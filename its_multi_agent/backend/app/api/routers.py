from agents.run import Runner
from fastapi.routing import APIRouter
from starlette.responses import StreamingResponse
from typing import AsyncGenerator

from infrastructure.logging.logger import logger
from multi_agent.orchestrator_agent import orchestrator_agent
from schemas.request import ChatMessageRequest, HumanApprovalRequest, UserSessionsRequest
from schemas.response import ContentKind
from services.agent_service import MultiAgentService
from services.guardrail_service import guardrail_service
from services.hitl_service import hitl_service
from services.session_service import session_service
from services.structured_output_service import structured_output_service
from utils.response_util import ResponseFactory

router = APIRouter()


@router.post("/api/query", summary="流式执行智能体")
async def query(request_context: ChatMessageRequest) -> StreamingResponse:
    user_id = request_context.context.user_id
    user_query = request_context.query

    # ========== Guardrail 输入过滤 ==========
    check_result = guardrail_service.check_input(user_query)
    if check_result.blocked:
        # 命中通用敏感词，直接拒绝
        return StreamingResponse(
            content=_blocked_stream(check_result),
            status_code=200,
            media_type="text/event-stream",
        )
    if check_result.replaced:
        # 命中业务敏感词，使用替换后的文本
        user_query = check_result.filtered_text
        logger.info(
            "Guardrail: user=%s business_words=%s replaced_query=%s",
            user_id,
            check_result.matched_business,
            user_query,
        )
    # ========== Guardrail 过滤结束 ==========

    logger.info("user=%s query=%s", user_id, user_query)
    async_generator_result = MultiAgentService.process_task(request_context, flag=True)
    return StreamingResponse(
        content=async_generator_result,
        status_code=200,
        media_type="text/event-stream",
    )


async def _blocked_stream(check_result) -> AsyncGenerator[str, None]:
    """返回敏感词拦截响应。"""
    yield "data: " + ResponseFactory.build_text(
        f"抱歉，您的输入包含敏感词（{', '.join(check_result.matched_common)}），已被系统拦截。",
        ContentKind.PROCESS,
    ).model_dump_json() + "\n\n"
    yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"


@router.post("/api/human_approval", summary="处理审批结果并恢复同一条 run")
async def human_approval(request: HumanApprovalRequest) -> StreamingResponse:
    # 这里不是重新构造一轮新的用户提问，
    # 而是拿回之前保存在 hitl_service 中的 pending approval，
    # 从同一条 run 的暂停点继续恢复。
    approval = hitl_service.resolve_pending_approval(
        token=request.approval_token,
        user_id=request.context.user_id,
        session_id=request.context.session_id or "",
        decision=request.decision,
    )

    async def approval_stream():
        if approval.decision == "rejected":
            # 拒绝时不再继续恢复 run，直接结束本轮流程。
            hitl_service.consume_approval(approval.token)
            yield "data: " + ResponseFactory.build_text(
                "你已拒绝此次敏感操作，本轮流程已停止。",
                ContentKind.PROCESS,
            ).model_dump_json() + "\n\n"
            yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"
            return

        try:
            # 这是官方文档里的恢复方式：
            # 1. 从之前保存的 state 中逐个 approve interruption
            # 2. 再把 state 重新交给 Runner.run(...)
            # 这样恢复的是“同一条 run”，不是重新向 Agent 发起新提问。
            if approval.state is None:
                raise ValueError("审批状态丢失，无法恢复运行")

            for interruption in approval.interruptions:
                approval.state.approve(interruption)

            result = await Runner.run(orchestrator_agent, approval.state)
            interruptions = list(getattr(result, "interruptions", None) or [])
            if interruptions:
                to_state = getattr(result, "to_state", None)
                next_state = to_state() if callable(to_state) else getattr(result, "state", None)
                next_pending = hitl_service.create_pending_approval(
                    user_id=request.context.user_id,
                    session_id=request.context.session_id or "",
                    query=approval.query,
                    state=next_state,
                    interruptions=interruptions,
                    title="需要人工确认",
                    question="是否允许智能体继续执行下一步敏感操作？",
                    details=f"继续执行请求：{approval.query}",
                    approve_label="继续",
                    reject_label="取消",
                )
                logger.info(
                    "[Approval] resumed run created next interruption token=%s count=%d",
                    next_pending.token,
                    len(interruptions),
                )
                yield "data: " + ResponseFactory.build_human_approval(
                    token=next_pending.token,
                    title=next_pending.title,
                    question=next_pending.question,
                    details=next_pending.details,
                    approve_label=next_pending.approve_label,
                    reject_label=next_pending.reject_label,
                ).model_dump_json() + "\n\n"
                yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"
                return

            final_output = result.final_output or ""
            structured_output = structured_output_service.parse_final_output(final_output)
            logger.info(
                "[Approval] resumed run token=%s final_output=%s structured_intent=%s",
                approval.token,
                final_output[:1000],
                structured_output.intent,
            )
            yield "data: " + ResponseFactory.build_text(
                structured_output.answer,
                ContentKind.ANSWER,
            ).model_dump_json() + "\n\n"
        finally:
            hitl_service.consume_approval(approval.token)

        yield "data: " + ResponseFactory.build_finish().model_dump_json() + "\n\n"

    return StreamingResponse(
        content=approval_stream(),
        status_code=200,
        media_type="text/event-stream",
    )


@router.post("/api/user_sessions")
def get_user_sessions(request: UserSessionsRequest):
    user_id = request.user_id
    logger.info("fetch sessions for user=%s", user_id)
    try:
        all_sessions = session_service.get_all_sessions_memory(user_id)
        return {
            "success": True,
            "user_id": user_id,
            "total_sessions": len(all_sessions),
            "sessions": all_sessions,
        }
    except Exception as exc:
        logger.error("fetch sessions failed user=%s error=%s", user_id, exc)
        return {
            "success": False,
            "user_id": user_id,
            "error": str(exc),
        }
