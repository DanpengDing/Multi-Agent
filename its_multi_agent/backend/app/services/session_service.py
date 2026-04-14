from json import JSONDecodeError
from typing import Any, Dict, List, Optional, Union

from infrastructure.logging.logger import logger
from repositories.session_repository import session_repository
from schemas.session_memory import SessionMemoryState
from services.context_compression_service import context_compression_service


class SessionService:
    DEFAULT_SESSION_ID = "default_session"

    def __init__(self):
        self._repo = session_repository

    async def load_runtime_state(
        self,
        user_id: str,
        session_id: str,
        pending_user_input: str = "",
    ) -> SessionMemoryState:
        target_session_id = session_id or self.DEFAULT_SESSION_ID
        state = self.load_session_state(user_id, target_session_id)
        runtime_state, triggered, should_persist = await context_compression_service.compress_state_if_needed(
            state,
            pending_user_input=pending_user_input,
        )

        if triggered:
            logger.info(
                "[SessionService] compression triggered user=%s session=%s should_persist=%s",
                user_id,
                target_session_id,
                should_persist,
            )

        if should_persist:
            self.save_session_state(user_id, target_session_id, runtime_state)

        return runtime_state

    def prepare_history(
        self,
        user_id: str,
        session_id: str,
        user_input: str,
        max_turn: int = 3,
        append_user_message: bool = True,
        base_history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        # 中文注释：这个方法保留旧签名是为了兼容现有调用方与测试，
        # 真正的运行时上下文现在优先通过结构化会话状态来构建，不再按固定 3 轮硬截断。
        if base_history is not None:
            chat_history = list(base_history)
        else:
            state = self.load_session_state(user_id, session_id)
            chat_history = self.build_runtime_history(state)

        if append_user_message:
            chat_history.append({"role": "user", "content": user_input})
        return chat_history

    def load_history(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        state = self.load_session_state(user_id, session_id)
        return self.build_runtime_history(state)

    def load_session_state(self, user_id: str, session_id: str) -> SessionMemoryState:
        target_session_id = session_id or self.DEFAULT_SESSION_ID
        try:
            session_payload = self._repo.load_session(user_id, target_session_id)
            return self._normalize_session_payload(session_payload, target_session_id)
        except JSONDecodeError as exc:
            logger.error("load session failed: user=%s session=%s error=%s", user_id, session_id, exc)
            return SessionMemoryState(
                system_messages=[
                    {
                        "role": "system",
                        "content": "会话历史已损坏，本轮仅基于当前可用信息继续处理。",
                    }
                ]
            )

    def save_session_state(self, user_id: str, session_id: str, state: SessionMemoryState):
        target_session_id = session_id or self.DEFAULT_SESSION_ID
        try:
            self._repo.save_session(user_id, target_session_id, state.model_dump())
        except Exception as exc:
            logger.error("save session failed: user=%s session=%s error=%s", user_id, session_id, exc)

    def append_message_to_state(self, state: SessionMemoryState, role: str, content: str) -> SessionMemoryState:
        new_state = state.model_copy(deep=True)
        new_state.messages.append({"role": role, "content": content})
        return new_state

    def build_runtime_history(
        self,
        state: SessionMemoryState,
        user_input: Optional[str] = None,
        append_user_message: bool = True,
    ) -> List[Dict[str, str]]:
        runtime_history = list(state.system_messages)
        if state.summary is not None:
            runtime_history.append(context_compression_service.format_summary_message(state.summary))
        runtime_history.extend(state.messages)
        if append_user_message and user_input:
            runtime_history.append({"role": "user", "content": user_input})
        return runtime_history

    def save_history(self, user_id: str, session_id: str, chat_history: List[Dict[str, Any]]):
        # 中文注释：这个兼容方法只在仍有旧调用方时兜底使用，
        # 它会把传入的消息列表重新归一成新的会话状态对象再保存。
        if chat_history is None:
            return
        target_session_id = session_id or self.DEFAULT_SESSION_ID
        try:
            normalized_state = self._normalize_session_payload(chat_history, target_session_id)
            self.save_session_state(user_id, target_session_id, normalized_state)
        except Exception as exc:
            logger.error("save session failed: user=%s session=%s error=%s", user_id, session_id, exc)

    def get_all_sessions_memory(self, user_id: str) -> List[Dict[str, Any]]:
        raw_sessions = self._repo.get_all_sessions_metadata(user_id)
        formatted_sessions = []

        for session_id, create_time, data_or_error in raw_sessions:
            session_item = {"session_id": session_id, "create_time": create_time}
            if isinstance(data_or_error, Exception):
                logger.error("load session metadata failed: %s %s", session_id, data_or_error)
                session_item.update({
                    "memory": [],
                    "total_messages": 0,
                    "error": "会话记录读取失败",
                })
            else:
                state = self._normalize_session_payload(data_or_error, session_id)
                user_visible_memory = [msg for msg in state.messages if msg.get("role") != "system"]
                session_item.update({
                    "memory": user_visible_memory,
                    "total_messages": len(user_visible_memory),
                    "summary": state.summary.model_dump() if state.summary else None,
                })
            formatted_sessions.append(session_item)

        formatted_sessions.sort(key=lambda item: item.get("create_time") or "", reverse=True)
        return formatted_sessions

    def _normalize_session_payload(
        self,
        payload: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]],
        session_id: str,
    ) -> SessionMemoryState:
        if payload is None:
            return SessionMemoryState(system_messages=self._init_system_msg_instruct(session_id))

        if isinstance(payload, list):
            system_messages = [msg for msg in payload if msg.get("role") == "system"]
            normal_messages = [msg for msg in payload if msg.get("role") != "system"]
            return SessionMemoryState(
                system_messages=system_messages or self._init_system_msg_instruct(session_id),
                messages=normal_messages,
            )

        if isinstance(payload, dict):
            raw_system_messages = payload.get("system_messages")
            raw_messages = payload.get("messages")
            raw_summary = payload.get("summary")
            if raw_system_messages is not None or raw_messages is not None or raw_summary is not None:
                return SessionMemoryState.model_validate(
                    {
                        "system_messages": raw_system_messages or self._init_system_msg_instruct(session_id),
                        "messages": raw_messages or [],
                        "summary": raw_summary,
                        "summary_version": payload.get("summary_version", 1),
                    }
                )

        # 中文注释：如果文件里是未知格式，就回退成初始化状态，避免因为脏数据阻断对话链路。
        logger.warning("[SessionService] unknown session payload format session=%s payload=%s", session_id, type(payload))
        return SessionMemoryState(system_messages=self._init_system_msg_instruct(session_id))

    def _init_system_msg_instruct(self, session_id: str) -> List[Dict[str, str]]:
        return [{
            "role": "system",
            "content": f"你是一个多智能体助手，请基于当前会话上下文回答用户问题。(session_id={session_id})",
        }]


session_service = SessionService()
