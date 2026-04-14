from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


class ContentKind(str, Enum):
    THINKING = "THINKING"
    PROCESS = "PROCESS"
    ANSWER = "ANSWER"
    # 这不是普通文本分片，而是“当前任务已暂停，等待人工确认”的专用事件类型。
    HUMAN_APPROVAL = "HUMAN_APPROVAL"


class StreamStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"


class StopReason(str, Enum):
    NORMAL = "NORMAL"
    MAX_TOKENS = "MAX_TOKENS"
    ERROR = "ERROR"


class MessageBody(BaseModel):
    contentType: str


class TextMessageBody(MessageBody):
    contentType: Literal["sagegpt/text"] = "sagegpt/text"
    text: str = Field(default="", description="文本内容")
    kind: ContentKind


class HumanApprovalBody(MessageBody):
    # 前端收到这个包体后，不应按普通对话文本渲染，
    # 而应展示审批卡片，并在用户确认后调用 /api/human_approval 继续执行。
    contentType: Literal["sagegpt/human_approval"] = "sagegpt/human_approval"
    kind: Literal[ContentKind.HUMAN_APPROVAL] = ContentKind.HUMAN_APPROVAL
    token: str
    title: str
    question: str
    approveLabel: str = "确认"
    rejectLabel: str = "取消"
    details: Optional[str] = None


class FinishMessageBody(MessageBody):
    contentType: Literal["sagegpt/finish"] = "sagegpt/finish"


class PacketMeta(BaseModel):
    createTime: str
    finishReason: Optional[StopReason] = None
    errorMessage: Optional[str] = None


class StreamPacket(BaseModel):
    id: str
    content: Union[TextMessageBody, HumanApprovalBody, FinishMessageBody]
    status: StreamStatus
    metadata: PacketMeta
