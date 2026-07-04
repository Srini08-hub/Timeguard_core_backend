"""
Node: fetch_parse
-----------------
Fetches the Gmail message, persists the Email record,
downloads each attachment, stores to disk, creates Attachment records.
Populates state with email_id and attachment_ids for downstream nodes.
"""

import asyncio
import logging
from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig

from src.control.agents.graph_config import get_db_session, get_gmail_service
from src.control.agents.state import AttachmentState, TimeguardState
from src.data.models.attachment import AttachmentStatus
from src.data.models.email import EmailStatus
from src.data.repositories.attachment_repository import AttachmentRepository
from src.data.repositories.email_repository import EmailRepository
from src.utils.storage import save_attachment

logger = logging.getLogger(__name__)

MIME_TYPE_MAPPING = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel",
    "application/vnd.ms-excel": "excel",
    "image/png": "image",
    "image/jpeg": "image",
    "image/jpg": "image",
}


async def fetch_parse_node(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    db_session = get_db_session(config)
    gmail_service = get_gmail_service(config)
    email_repo = EmailRepository(db_session)
    attachment_repo = AttachmentRepository(db_session)

    logger.info("Fetching Gmail message %s", state["gmail_message_id"])
    try:
        raw = await asyncio.to_thread(
            gmail_service.fetch_email,
            state["gmail_message_id"],
        )
    except Exception as exc:
        logger.exception(
            "Failed to fetch Gmail message %s",
            state["gmail_message_id"],
        )
        # email = await email_repo.create_failed_fetch(
        #     gmail_message_id=state["gmail_message_id"],
        #     failure_stage="fetch_email",
        #     failure_reason=str(exc),
        #     received_at=datetime.now(UTC),
        # )
        # await db_session.commit()

        return TimeguardState(
            gmail_message_id=state["gmail_message_id"],
            attachment_ids=[],
            attachments=[],
            error=str(exc),
            blocks=[],
            current_excel_block_index=0,
            results=[],
            d_blocks=[],
        )

    received_at = datetime.fromtimestamp(raw.received_at_ms / 1000, tz=UTC)
    email = await email_repo.create(
        gmail_message_id=raw.gmail_message_id,
        gmail_thread_id=raw.gmail_thread_id,
        sender_email=raw.sender_email,
        subject=raw.subject,
        body=raw.body_text,
        received_at=received_at,
    )

    attachment_ids = []
    attachments_state = []

    for raw_att in raw.attachments:
        document_type = MIME_TYPE_MAPPING.get(raw_att.mime_type)
        if document_type is None:
            logger.info("Unsupported MIME type", raw_att.mime_type)
        else:
            attachment = await attachment_repo.create(
                email_id=email.email_id,
                filename=raw_att.filename,
                document_type=document_type,
                status=AttachmentStatus.PENDING,
            )
            await db_session.commit()

            try:
                attachment_bytes = await asyncio.to_thread(
                    gmail_service.download_attachment,
                    raw.gmail_message_id,
                    raw_att.gmail_attachment_id,
                )
                public_url, file_path = save_attachment(attachment_bytes, raw_att.filename)
                await attachment_repo.set_url_and_status(
                    attachment,
                    url=public_url,
                    status=AttachmentStatus.PENDING,
                )
                await db_session.commit()

                attachments_state.append(
                    AttachmentState(
                        file_name=raw_att.filename,
                        file_path=file_path,
                        doc_type=document_type,
                        attachment_url=public_url,
                        attachment_db_id=attachment.attachment_id,
                        status=AttachmentStatus.PENDING.value,
                    )
                )
            except Exception as exc:
                logger.exception("Failed to download %s", raw_att.filename)
                # await attachment_repo.set_failed(
                #     attachment,
                #     failure_stage="download",
                #     failure_reason=str(exc),
                # )
                await email_repo.set_status(
                    email,
                    EmailStatus.FAILED,
                    failure_stage="attachment_download",
                    failure_reason=str(exc),
                )
                await db_session.commit()
            attachment_ids.append(attachment.attachment_id)

    logger.info(
        "fetch_parse_node done: email_id=%s, %d attachment(s)",
        email.email_id,
        len(attachment_ids),
    )

    return TimeguardState(
        gmail_message_id=state["gmail_message_id"],
        sender_mail=email.sender_email,
        body=email.body or "",
        subject=email.subject or "",
        email_id=email.email_id,
        attachment_ids=attachment_ids,
        attachments=attachments_state,
        blocks=[],
        current_excel_block_index=0,
        results=[],
        d_blocks=[],
    )
