import uuid
from datetime import datetime
from typing import Optional

from schemas.response import (
    ContentKind,
    FinishMessageBody,
    HumanApprovalBody,
    PacketMeta,
    StreamPacket,
    StreamStatus,
    TextMessageBody,
)


class ResponseFactory:
    @staticmethod
    def build_text(text: str, kind: ContentKind) -> StreamPacket:
        body = TextMessageBody(text=text, kind=kind)
        return StreamPacket(
            id=str(uuid.uuid4()),
            content=body,
            status=StreamStatus.IN_PROGRESS,
            metadata=PacketMeta(createTime=str(datetime.now()))
        )

    @staticmethod
    def build_human_approval(
        token: str,
        title: str,
        question: str,
        details: Optional[str] = None,
        approve_label: str = "确认",
        reject_label: str = "取消",
    ) -> StreamPacket:
        body = HumanApprovalBody(
            token=token,
            title=title,
            question=question,
            details=details,
            approveLabel=approve_label,
            rejectLabel=reject_label,
        )
        return StreamPacket(
            id=str(uuid.uuid4()),
            content=body,
            status=StreamStatus.IN_PROGRESS,
            metadata=PacketMeta(createTime=str(datetime.now()))
        )

    @staticmethod
    def build_finish(message_id: Optional[str] = None) -> StreamPacket:
        return StreamPacket(
            id=message_id or str(uuid.uuid4()),
            content=FinishMessageBody(),
            status=StreamStatus.FINISHED,
            metadata=PacketMeta(createTime=str(datetime.now()))
        )
