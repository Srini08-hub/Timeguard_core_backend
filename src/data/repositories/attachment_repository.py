import logging
from uuid import UUID

from sqlalchemy.orm import Session

from src.data.models.attachment import Attachment, AttachmentStatus

logger = logging.getLogger(__name__)


class AttachmentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        *,
        email_id: UUID,
        filename: str,
        document_type: str | None,
        status: AttachmentStatus = AttachmentStatus.PENDING,
    ) -> Attachment:
        attachment = Attachment(
            email_id=email_id,
            attachment_url="",  # placeholder until file is saved
            file_name=filename,
            document_type=document_type,
            status=status,
        )
        self._db.add(attachment)
        self._db.flush()
        logger.info(
            "Created Attachment record %s for email_id=%s",
            attachment.attachment_id,
            email_id,
        )
        return attachment

    def set_url_and_status(
        self,
        attachment: Attachment,
        *,
        url: str,
        status: AttachmentStatus,
    ) -> None:
        attachment.attachment_url = url
        attachment.status = status
        self._db.flush()

    def get_by_id(self, attachment_id: UUID) -> Attachment | None:
        return self._db.get(Attachment, attachment_id)

    def set_status(
        self,
        attachment: Attachment,
        *,
        status: AttachmentStatus,
    ) -> None:
        attachment.status = status
        self._db.flush()

    def set_failed(
        self,
        attachment: Attachment,
        *,
        failure_stage: str,
        failure_reason: str,
    ) -> None:
        attachment.status = AttachmentStatus.FAILED
        attachment.failure_stage = failure_stage
        attachment.failure_reason = failure_reason
        self._db.flush()
