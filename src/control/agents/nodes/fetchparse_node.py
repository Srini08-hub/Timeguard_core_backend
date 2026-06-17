"""
Node: fetch_parse
-----------------
Fetches the Gmail message, persists the Email record,
downloads each attachment, stores to disk, creates Attachment records.
Populates state with email_id and attachment_ids for downstream nodes.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from src.control.agents.state import AttachmentState, TimeguardState
from src.core.services.gmail_service import GmailService
from src.data.models.attachment import AttachmentStatus
from src.data.repositories.attachment_repository import AttachmentRepository
from src.data.repositories.email_repository import EmailRepository
from src.utils.storage import save_attachment

logger = logging.getLogger(__name__)

MIME_TYPE_MAPPING = {
    "application/pdf": "pdf",
    # Excel
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel",
    # .xlsx
    "application/vnd.ms-excel": "excel",
    # .xls
    # Images
    "image/png": "image",
    "image/jpeg": "image",
    "image/jpg": "image",
}


def build_fetch_parse_node(
    gmail_service: GmailService, db_session: Any
) -> Callable[[TimeguardState], TimeguardState]:
    """Factory that closes over dependencies. Accepts a SQLAlchemy session factory.
    Returns a plain callable compatible with LangGraph node signature.
    """
    """
    Factory that closes over dependencies.
    Returns a plain callable compatible with LangGraph node signature.
    """

    def fetch_parse_node(state: TimeguardState) -> TimeguardState:
        email_repo = EmailRepository(db_session)
        attachment_repo = AttachmentRepository(db_session)

        # --- Idempotency guard -------------------------------------------
        existing = email_repo.get_by_gmail_message_id(state["gmail_message_id"])
        if existing:
            logger.info("Already ingested %s, skipping.", state["gmail_message_id"])

            attachments_state = []
            for a in existing.attachments:
                attachments_state.append(
                    AttachmentState(
                        gmail_attachment_id="",  # Not stored in DB
                        file_name=a.file_name,
                        doc_type=a.document_type or "",
                        attachment_url=a.attachment_url,
                        attachment_db_id=a.attachment_id,
                        status=a.status,
                    )
                )

            return TimeguardState(
                gmail_message_id=state["gmail_message_id"],
                email_id=existing.email_id,
                attachment_ids=[a.attachment_id for a in existing.attachments],
                attachments=attachments_state,
            )

        # --- 1. Fetch from Gmail -----------------------------------------
        logger.info("Fetching Gmail message %s", state["gmail_message_id"])
        raw = gmail_service.fetch_email(state["gmail_message_id"])

        # --- 2. Persist Email record -------------------------------------
        received_at = datetime.fromtimestamp(raw.received_at_ms / 1000, tz=UTC)
        email = email_repo.create(
            gmail_message_id=raw.gmail_message_id,
            gmail_thread_id=raw.gmail_thread_id,
            sender_email=raw.sender_email,
            subject=raw.subject,
            body=raw.body_text,
            received_at=received_at,
        )

        # --- 3. Process each attachment ----------------------------------
        attachment_ids = []
        attachments_state = []

        for raw_att in raw.attachments:
            document_type = MIME_TYPE_MAPPING.get(raw_att.mime_type)
            if document_type is None:
                logger.info("Unsupported MIME type", raw_att.mime_type)
                # attachments_state.append(
                #     AttachmentState(
                #         gmail_attachment_id=raw_att.gmail_attachment_id,
                #         file_name=raw_att.filename,
                #         status=AttachmentStatus.NOT_SUPPORTED_DOCUMENT,
                #     )
                # )
            else:
                attachment = attachment_repo.create(
                    email_id=email.email_id,
                    filename=raw_att.filename,
                    document_type=document_type,
                    status=AttachmentStatus.PENDING,
                )
                try:
                    attachment_bytes = gmail_service.download_attachment(
                        raw.gmail_message_id,
                        raw_att.gmail_attachment_id,
                    )
                    public_url, _ = save_attachment(attachment_bytes, raw_att.filename)
                    attachment_repo.set_url_and_status(
                        attachment,
                        url=public_url,
                        status=AttachmentStatus.PENDING,
                    )

                    attachments_state.append(
                        AttachmentState(
                            gmail_attachment_id=raw_att.gmail_attachment_id,
                            file_name=raw_att.filename,
                            doc_type=document_type,
                            attachment_url=public_url,
                            attachment_db_id=attachment.attachment_id,
                            status=AttachmentStatus.PENDING,
                        )
                    )
                except Exception as exc:
                    logger.exception("Failed to download %s", raw_att.filename)
                    attachment_repo.set_failed(
                        attachment,
                        failure_stage="download",
                        failure_reason=str(exc),
                    )
            attachment_ids.append(attachment.attachment_id)

        # --- 4. Finish ---------------------------------------------------
        logger.info(
            "fetch_parse_node done: email_id=%s, %d attachment(s)",
            email.email_id,
            len(attachment_ids),
        )

        return TimeguardState(
            gmail_message_id=state["gmail_message_id"],
            sender_mail=email.sender_email,
            body=email.body or "",
            email_id=email.email_id,
            attachment_ids=attachment_ids,
            attachments=attachments_state,
        )

    return fetch_parse_node
