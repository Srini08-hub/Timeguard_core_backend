import logging
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.timesheet import Timesheet

logger = logging.getLogger(__name__)


class TimesheetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_pending_timesheets(self) -> list[Timesheet]:
        result = await self._session.execute(
            select(Timesheet)
            .where(Timesheet.status == "pending")
            .order_by(Timesheet.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_source(
        self,
        *,
        email_id: UUID,
        source_type: str,
        attachment_id: UUID | None,
    ) -> Timesheet | None:
        stmt = select(Timesheet).where(
            Timesheet.email_id == email_id,
            Timesheet.source_type == source_type,
        )
        if attachment_id is None:
            stmt = stmt.where(Timesheet.attachment_id.is_(None))
        else:
            stmt = stmt.where(Timesheet.attachment_id == attachment_id)

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        email_id: UUID,
        source_type: str,
        attachment_id: UUID | None = None,
        status: str = "pending",
    ) -> Timesheet:
        timesheet = Timesheet(
            email_id=email_id,
            attachment_id=attachment_id,
            source_type=source_type,
            status=status,
        )
        self._session.add(timesheet)
        await self._session.flush()
        logger.info(
            "Created Timesheet record %s for email_id=%s source_type=%s "
            "attachment_id=%s",
            timesheet.timesheet_id,
            email_id,
            source_type,
            attachment_id,
        )
        return timesheet

    async def create_if_not_exists(
        self,
        *,
        email_id: UUID,
        source_type: str,
        attachment_id: UUID | None = None,
        status: str = "pending",
    ) -> Timesheet:
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
            status=status,
        )

    async def create_for_classified_sources(
        self,
        *,
        email_id: UUID,
        body_is_timesheet: bool,
        timesheet_attachment_ids: list[UUID],
    ) -> list[Timesheet]:
        created_records: list[Timesheet] = []

        if body_is_timesheet:
            created = await self.create_if_not_exists(
                email_id=email_id,
                source_type="body",
                attachment_id=None,
                status="pending",
            )
            created_records.append(created)

        for attachment_id in timesheet_attachment_ids:
            created = await self.create_if_not_exists(
                email_id=email_id,
                source_type="attachment",
                attachment_id=attachment_id,
                status="pending",
            )
            created_records.append(created)

        return created_records

    async def set_extracted_payload(
        self,
        *,
        timesheet_id: UUID,
        extracted_payload: Any,
    ) -> Timesheet | None:
        timesheet = await self._session.get(Timesheet, timesheet_id)
        if timesheet is None:
            logger.warning(
                "Timesheet %s not found when saving extracted payload",
                timesheet_id,
            )
            return None

        timesheet.extracted_payload = extracted_payload
        await self._session.flush()
        logger.info("Updated Timesheet %s extracted_payload", timesheet_id)
        return timesheet

    async def append_extracted_payload(
        self,
        *,
        timesheet_id: UUID,
        parsed_payload: Any,
    ) -> Timesheet | None:
        timesheet = await self._session.get(Timesheet, timesheet_id)
        if timesheet is None:
            logger.warning(
                "Timesheet %s not found when appending extracted payload",
                timesheet_id,
            )
            return None

        current_payload = timesheet.extracted_payload
        if current_payload is None:
            timesheet.extracted_payload = cast(Any, [parsed_payload])
        elif isinstance(current_payload, list):
            current_payload.append(parsed_payload)
            timesheet.extracted_payload = cast(Any, current_payload)
        else:
            timesheet.extracted_payload = cast(Any, [current_payload, parsed_payload])

        await self._session.flush()
        logger.info("Appended parsed payload to Timesheet %s", timesheet_id)
        return timesheet
