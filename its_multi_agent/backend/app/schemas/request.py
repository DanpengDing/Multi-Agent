from typing import Literal, Optional

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    user_id: str
    session_id: Optional[str] = Field(default=None, description="会话 ID")


class ChatMessageRequest(BaseModel):
    # 用户当前输入的原始问题。
    # 这句话会先进入 query 重写流程，再把补全后的结果交给主 Agent。
    query: str
    context: UserContext
    flag: bool = True
    # 当主流程触发人工审批时，后端会把审批 token 带回续跑请求。
    # 这样系统就能知道这不是一条全新的问题，而是上一轮流程的继续执行。
    approval_token: Optional[str] = Field(default=None, description="HITL 审批 token")
    # 只有人工审批回调才会带这个字段。
    # Agent 工具层会根据它判断：这次是否已经得到用户批准。
    approval_decision: Optional[Literal["approved", "rejected"]] = Field(
        default=None,
        description="HITL 审批结果"
    )
    # 续跑时沿用的是原 query，所以这里要避免再次追加一条重复的 user 消息。
    # 否则历史中会出现两条一模一样的问题，导致上下文污染。
    skip_user_message: bool = Field(
        default=False,
        description="是否跳过将当前 query 追加为新的 user 消息"
    )


class UserSessionsRequest(BaseModel):
    user_id: str = Field(description="用户 ID")


class HumanApprovalRequest(BaseModel):
    approval_token: str = Field(description="待审批记录 token")
    decision: Literal["approved", "rejected"] = Field(description="审批结果")
    context: UserContext
