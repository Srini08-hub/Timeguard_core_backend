import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.attachment import Attachment, AttachmentStatus

logger = logging.getLogger(__name__)


class AttachmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        email_id: UUID,
        filename: str,
        document_type: str | None,
        status: AttachmentStatus = AttachmentStatus.PENDING,
    ) -> Attachment:
        attachment = Attachment(
            email_id=email_id,
            attachment_url="",
            file_name=filename,
            document_type=document_type,
            status=status,
        )
        self._session.add(attachment)
        await self._session.flush()
        logger.info(
            "Created Attachment record %s for email_id=%s",
            attachment.attachment_id,
            email_id,
        )
        return attachment

    async def set_url_and_status(
        self,
        attachment: Attachment,
        *,
        url: str,
        status: AttachmentStatus,
    ) -> None:
        attachment.attachment_url = url
        attachment.status = status
        await self._session.flush()

    async def get_by_id(self, attachment_id: UUID) -> Attachment | None:
        return await self._session.get(Attachment, attachment_id)

    async def set_status(
        self,
        attachment: Attachment,
        *,
        status: AttachmentStatus,
    ) -> None:
        attachment.status = status
        await self._session.flush()

    async def set_failed(
        self,
        attachment: Attachment,
        *,
        failure_stage: str,
        failure_reason: str,
    ) -> None:
        attachment.status = AttachmentStatus.FAILED
        attachment.failure_stage = failure_stage
        attachment.failure_reason = failure_reason
        await self._session.flush()
