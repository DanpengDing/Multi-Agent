import re
import traceback
from collections.abc import AsyncGenerator

from agents.run import RunConfig, Runner
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from infrastructure.logging.logger import logger
from infrastructure.tracing import get_tracer
from multi_agent.orchestrator_agent import orchestrator_agent
from schemas.request import ChatMessageRequest
from schemas.response import ContentKind
from services.hitl_service import hitl_service
from services.query_rewrite_service import query_rewrite_service
from services.session_service import session_service
from services.structured_output_service import structured_output_service
from services.stream_response_service import process_stream_response
from utils.response_util import ResponseFactory


class MultiAgentService:
    @staticmethod
    def _normalize_final_output(raw_output: str):
        # 中文注释：主 Agent 目前仍以自然语言输出为主，
        # 所以这里统一做一次结构化归一，保证后端后续处理拿到稳定字段。
        return structured_output_service.parse_final_output(raw_output)

    @staticmethod
    def _extract_interruptions(result) -> list:
        # OpenAI Agents SDK 在 run 因审批暂停时，会把待审批项放到 result.interruptions。
        interruptions = getattr(result, "interruptions", None)
        return list(interruptions) if interruptions else []

    @staticmethod
    def _extract_state(result):
        # 官方文档推荐用 result.to_state() 获取可恢复的 run 状态。
        # 某些版本也可能直接暴露 result.state，所以这里做一层兼容包装。
        to_state = getattr(result, "to_state", None)
        if callable(to_state):
            return to_state()
        return getattr(result, "state", None)

    @classmethod
    async def process_task(cls, request: ChatMessageRequest, flag: bool) -> AsyncGenerator[str, None]:
        # flag 不是业务参数，而是本次调用是否还允许自动重试一次的开关。
        # 第一次从 /api/query 进入时，外层会传 flag=True，表示如果本轮中途抛异常，可以再自动补跑一次。
        # 一旦进入补跑分支，下面会把 flag 改成 False 再调用自己，这样第二次如果还失败，就不会继续无限递归。
        tracer = get_tracer("multi-agent-service")
        user_id = request.context.user_id
        session_id = request.context.session_id or ""
        original_query = request.query
        user_query = original_query

        try:
            logger.info(
                "[AgentService] start user=%s session=%s retry=%s skip_user_message=%s query=%s",
                user_id,
                session_id,
                flag,
                request.skip_user_message,
                original_query,
            )

            # 第 1 步：先加载历史消息，再做 query rewrite。
            # 这里的 rewrite 不是审批逻辑的一部分，只是让主调度智能体拿到更完整的当前问题。
            with tracer.start_as_current_span(
                "query_rewrite",
                kind=SpanKind.INTERNAL,
                attributes={
                    "user.id": user_id,
                    "session.id": session_id,
                    "query.original": original_query,
                }
            ) as span:
                runtime_state = await session_service.load_runtime_state(
                    user_id=user_id,
                    session_id=session_id,
                    pending_user_input=original_query,
                )
                base_history = session_service.build_runtime_history(runtime_state, append_user_message=False)
                rewrite_result = await query_rewrite_service.rewrite(original_query, base_history)
                user_query = rewrite_result.rewritten_query
                span.set_attribute("query.rewritten", user_query)
                span.set_attribute("query.history_length", len(base_history))
                logger.info(
                    "[AgentService] query rewritten user=%s session=%s original=%s rewritten=%s",
                    user_id,
                    session_id,
                    original_query,
                    user_query,
                )

            # 第 2 步：把最终 rewrite 后的 query 放入会话历史。
            # 这样主调度智能体拿到的是"本轮真正要处理的问题"。
            chat_history = session_service.build_runtime_history(
                runtime_state,
                user_input=user_query,
                append_user_message=not request.skip_user_message,
            )
            logger.debug(
                "[AgentService] prepared history user=%s session=%s messages=%d",
                user_id,
                session_id,
                len(chat_history),
            )

            if not request.skip_user_message:
                runtime_state = session_service.append_message_to_state(runtime_state, "user", user_query)
                session_service.save_session_state(user_id, session_id, runtime_state)

            # 这段是 query rewrite 的过程说明，前端会把它显示成 PROCESS 类型消息。
            for chunk in build_process_chunks(query_rewrite_service.build_process_message(rewrite_result)):
                yield chunk

            # 第 3 步：运行主调度智能体。
            # 这里 run_streamed 的职责只有一个：把主 Agent 的流式事件持续往外发。
            with tracer.start_as_current_span(
                "orchestrator.run",
                kind=SpanKind.INTERNAL,
                attributes={
                    "user.id": user_id,
                    "session.id": session_id,
                    "orchestrator.max_turns": 5,
                    "chat_history.length": len(chat_history),
                }
            ) as span:
                streaming_result = Runner.run_streamed(
                    starting_agent=orchestrator_agent,
                    input=chat_history,
                    context=user_query,
                    max_turns=5,
                    run_config=RunConfig(tracing_disabled=True),
                )
                logger.info(
                    "[AgentService] orchestrator started user=%s session=%s",
                    user_id,
                    session_id,
                )

                async for chunk in process_stream_response(streaming_result):
                    yield chunk

            # 第 4 步：流跑完后，检查官方 SDK 是否返回了审批中断。
            # 官方审批模式下，不会抛我们自定义异常，而是：
            # 1. 工具先不执行
            # 2. run 返回 interruptions + resumable state
            interruptions = cls._extract_interruptions(streaming_result)
            if interruptions:
                with tracer.start_as_current_span(
                    "hitl.approval_required",
                    kind=SpanKind.INTERNAL,
                    attributes={
                        "user.id": user_id,
                        "session.id": session_id,
                        "hitl.interruption_count": len(interruptions),
                    }
                ):
                    state = cls._extract_state(streaming_result)
                    logger.info(
                        "[AgentService] approval interruption user=%s session=%s count=%d",
                        user_id,
                        session_id,
                        len(interruptions),
                    )

                    pending = hitl_service.create_pending_approval(
                        user_id=user_id,
                        session_id=session_id,
                        query=user_query,
                        state=state,
                        interruptions=interruptions,
                        title="需要人工确认",
                        question="是否允许智能体查询维修站并继续执行？",
                        details=f"待执行请求：{user_query}",
                        approve_label="允许查询",
                        reject_label="取消操作",
                    )

                    yield "data: " + ResponseFactory.build_human_approval(
                        token=pending.token,
                        title=pending.title,
                        question=pending.question,
                        details=pending.details,
                        approve_label=pending.approve_label,
                        reject_label=pending.reject_label,
                    ).model_dump_json() + "\n\n"
                    yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"
                    return

            # 第 5 步：如果没有 interruptions，说明本轮 run 正常结束了。
            agent_result = streaming_result.final_output or ""
            structured_result = cls._normalize_final_output(agent_result)
            logger.info(
                "[AgentService] orchestrator finished user=%s session=%s final_output=%s structured_intent=%s",
                user_id,
                session_id,
                agent_result[:500],
                structured_result.intent,
            )

            # 中文注释：对外展示仍然优先使用 answer 字段，
            # 这样以后如果主 Agent 升级为真正 JSON 输出，前端也不用跟着一起改。
            formatted_result = re.sub(r"\n+", "\n", structured_result.answer)
            runtime_state = session_service.append_message_to_state(runtime_state, "assistant", formatted_result)
            session_service.save_session_state(user_id, session_id, runtime_state)
            yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"

        except Exception as exc:
            # 这里捕获的是"整条 process_task 链路"里的异常，
            # 比如 query rewrite、主 Agent 执行、流式事件处理等任一步骤抛错，都会进入这里。
            logger.error(
                "[AgentService] failed user=%s session=%s query=%s error=%s",
                user_id,
                session_id,
                original_query,
                exc,
            )
            logger.debug("[AgentService] traceback=%s", traceback.format_exc())

            # 记录异常到链路追踪
            span = trace.get_current_span()
            span.record_exception(exc)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))

            text = f"系统处理请求时出现异常：{exc}"
            yield "data: " + ResponseFactory.build_text(text, ContentKind.PROCESS).model_dump_json() + "\n\n"

            if flag:
                # 第一次失败时会进入这里。
                # 做法不是"只重试失败的那个工具"，而是重新调用整个 process_task，
                # 让本轮请求从头再走一遍：
                # 1. 重新加载会话历史
                # 2. 重新做 query rewrite
                # 3. 重新执行 orchestrator Agent
                # 4. 重新处理流式输出和 HITL 中断
                #
                # 之所以看起来像"递归重试"，是因为当前函数再次调用了自己：
                # async for item in MultiAgentService.process_task(request, flag=False)
                #
                # 关键点在于第二次调用时 flag=False，
                # 所以如果补跑这一轮还失败，就不会再进入这个 if，而是直接结束。
                # 因此最终最多只会执行 2 轮：首次执行 1 次 + 自动补跑 1 次。
                logger.info(
                    "[AgentService] retry once user=%s session=%s query=%s",
                    user_id,
                    session_id,
                    original_query,
                )
                retry_text = "正在尝试自动重试一次，请稍候。"
                yield "data: " + ResponseFactory.build_text(retry_text, ContentKind.PROCESS).model_dump_json() + "\n\n"
                async for item in MultiAgentService.process_task(request, flag=False):
                    yield item
            else:
                # 走到这里，说明当前已经是"补跑后的第二轮"了，或者外部本来就不允许重试。
                # 这时不再继续递归，而是直接给前端发送 finish，结束本次请求。
                yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"


def build_process_chunks(message: str):
    if not message:
        return
    yield "data: " + ResponseFactory.build_text(message, ContentKind.PROCESS).model_dump_json() + "\n\n"
