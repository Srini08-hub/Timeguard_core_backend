import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.attachment import Attachment
from src.data.models.content_extract import ContentExtract

logger = logging.getLogger(__name__)


class ContentExtractRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # async def get_pending_timesheets(self) -> list[Timesheet]:
    #     result = await self._session.execute(
    #         select(Timesheet)
    #         .where(Timesheet.status == "pending")
    #         .order_by(Timesheet.created_at.desc())
    #     )
    #     return list(result.scalars().all())

    async def get_by_source(
        self,
        *,
        email_id: UUID,
        source_type: str,
        attachment_id: UUID | None,
    ) -> ContentExtract | None:
        stmt = select(ContentExtract).where(
            ContentExtract.email_id == email_id,
            ContentExtract.source_type == source_type,
        )
        if attachment_id is None:
            stmt = stmt.where(ContentExtract.attachment_id.is_(None))
        else:
            stmt = stmt.where(ContentExtract.attachment_id == attachment_id)

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        email_id: UUID,
        source_type: str,
        attachment_id: UUID | None = None,
    ) -> ContentExtract:
        content_extract = ContentExtract(
            email_id=email_id,
            attachment_id=attachment_id,
            source_type=source_type,
        )
        self._session.add(content_extract)
        await self._session.flush()
        logger.info(
            "Created ContentExtract record %s for email_id=%s source_type=%s attachment_id=%s",
            content_extract.content_extract_id,
            email_id,
            source_type,
            attachment_id,
        )
        return content_extract

    async def create_if_not_exists(
        self,
        *,
        email_id: UUID,
        source_type: str,
        attachment_id: UUID | None = None,
    ) -> ContentExtract:
        existing = await self.get_by_source(
            email_id=email_id,
            source_type=source_type,
            attachment_id=attachment_id,
        )
        if existing is not None:
            return existing

        return await self.create(
            email_id=email_id,
            source_type=source_type,
            attachment_id=attachment_id,
        )

    async def create_for_classified_sources(
        self,
        *,
        email_id: UUID,
        body_is_timesheet: bool,
        timesheet_attachment_ids: list[UUID],
    ) -> list[ContentExtract]:
        created_records: list[ContentExtract] = []

        if body_is_timesheet:
            created = await self.create_if_not_exists(
                email_id=email_id,
                source_type="body",
                attachment_id=None,
            )
            created_records.append(created)

        for attachment_id in timesheet_attachment_ids:
            created = await self.create_if_not_exists(
                email_id=email_id, source_type="attachment", attachment_id=attachment_id
            )
            created_records.append(created)

        return created_records

    async def set_extracted_payload(
        self,
        *,
        content_extract_id: UUID,
        extracted_payload: Any,
    ) -> ContentExtract | None:
        content_extract = await self._session.get(ContentExtract, content_extract_id)
        if content_extract is None:
            logger.warning(
                "ContentExtract %s not found when saving extracted payload",
                content_extract_id,
            )
            return None

        content_extract.extracted_payload = extracted_payload
        await self._session.flush()
        logger.info("Updated ContentExtract %s extracted_payload", content_extract_id)
        return content_extract

    async def append_extracted_payload(
        self,
        *,
        content_extract_id: UUID,
        parsed_payload: Any,
    ) -> ContentExtract | None:
        content_extract = await self._session.get(ContentExtract, content_extract_id)
        if content_extract is None:
            logger.warning(
                "ContentExtract %s not found when appending extracted payload",
                content_extract_id,
            )
            return None

        current_payload = content_extract.extracted_payload
        logger.info(
            "Before append - content_extract_id: %s, "
            "current_payload type: %s, current_payload length: %s",
            content_extract_id,
            type(current_payload),
            len(current_payload) if isinstance(current_payload, list) else "N/A",
        )

        # if current_payload is None:
        #     content_extract.extracted_payload = cast(Any, [parsed_payload])
        #     logger.info("Initialized payload as list with first item")
        # elif isinstance(current_payload, list):
        #     current_payload.append(parsed_payload)
        #     content_extract.extracted_payload = cast(Any, current_payload)
        #     logger.info("Appended to existing list, new length: %s",
        # len(current_payload))
        # else:
        #     content_extract.extracted_payload = cast(Any,
        #  [current_payload, parsed_payload])
        #     logger.info("Converted non-list payload to list and appended")

        # await self._session.flush()
        if current_payload is None:
            content_extract.extracted_payload = [parsed_payload]

        elif isinstance(current_payload, list):
            content_extract.extracted_payload = current_payload + [parsed_payload]

        else:
            content_extract.extracted_payload = [current_payload, parsed_payload]

        await self._session.flush()
        logger.info(
            "After flush - content_extract_id: %s, payload type: %s, payload length: %s",
            content_extract_id,
            type(content_extract.extracted_payload),
            len(content_extract.extracted_payload)
            if isinstance(content_extract.extracted_payload, list)
            else "N/A",
        )
        return content_extract

    async def get_extracted_data_for_merge(
        self,
        *,
        email_id: UUID,
    ) -> list[dict[str, Any]]:
        """Load extracted data for merging, including attachment names.

        Args:
            email_id: The email ID to query

        Returns:
            List of dictionaries with extracted_payload, source_type,
             and attachment_name
        """
        stmt = (
            select(ContentExtract, Attachment.file_name)
            .outerjoin(Attachment, ContentExtract.attachment_id == Attachment.attachment_id)
            .where(ContentExtract.email_id == email_id)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        extracted_data = []
        for content_extract, file_name in rows:
            extracted_data.append(
                {
                    "extracted_payload": content_extract.extracted_payload,
                    "source_type": content_extract.source_type,
                    "attachment_name": file_name if file_name else "email_body",
                }
            )

        logger.info(
            "Loaded %d extracted data records for email %s",
            len(extracted_data),
            email_id,
        )
        return extracted_data
