import uuid
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional


@dataclass
class PendingApproval:
    # 这不是 OpenAI SDK 内置的对象，而是我们自己保存到内存中的“待审批记录”。
    # 目的只有一个：把官方 SDK 返回的 state / interruptions 暂存起来，
    # 等前端点击“同意”或“拒绝”后，再从同一条 run 继续恢复。
    token: str
    user_id: str
    session_id: str
    query: str
    title: str
    question: str
    details: Optional[str]
    approve_label: str
    reject_label: str
    state: Any
    interruptions: list[Any]
    decision: Optional[Literal["approved", "rejected"]] = None


class HitlService:
    def __init__(self):
        # 当前实现先放在内存里，适合本地调试和单实例服务。
        # 如果后面要做多实例部署，可以把这层替换成 Redis / DB。
        self._pending: Dict[str, PendingApproval] = {}

    def create_pending_approval(
        self,
        user_id: str,
        session_id: str,
        query: str,
        state: Any,
        interruptions: list[Any],
        title: str = "需要人工确认",
        question: str = "是否允许智能体继续执行该敏感操作？",
        details: Optional[str] = None,
        approve_label: str = "确认",
        reject_label: str = "取消",
    ) -> PendingApproval:
        # 官方审批模式里，真正关键的数据是：
        # 1. result.interruptions：本次被暂停的审批项
        # 2. result.to_state()：后续恢复同一条 run 的状态快照
        # 我们把这两样和用户上下文绑在一起，生成一个 token 返回给前端。
        token = str(uuid.uuid4())
        approval = PendingApproval(
            token=token,
            user_id=user_id,
            session_id=session_id or "",
            query=query,
            title=title,
            question=question,
            details=details,
            approve_label=approve_label,
            reject_label=reject_label,
            state=state,
            interruptions=list(interruptions or []),
        )
        self._pending[token] = approval
        return approval

    def resolve_pending_approval(
        self,
        token: str,
        user_id: str,
        session_id: str,
        decision: Literal["approved", "rejected"],
    ) -> PendingApproval:
        #先根据 token 找回之前保存的 PendingApproval：
        approval = self._pending.get(token)
        if approval is None:
            raise ValueError("审批记录不存在或已失效")
        if approval.user_id != user_id:
            raise ValueError("审批用户不匹配")
        if (approval.session_id or "") != (session_id or ""):
            raise ValueError("审批会话不匹配")

        approval.decision = decision
        return approval

    def consume_approval(self, token: str) -> None:
        # 一旦审批已经处理完成，就立刻删除，避免同一个 token 被重复使用。
        self._pending.pop(token, None)


hitl_service = HitlService()
