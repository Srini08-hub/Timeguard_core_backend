from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.exception import (
    ExceptionSeverity,
    ExceptionType,
    TimecardException,
)

ExceptionCreateEntry = tuple[ExceptionSeverity, ExceptionType, str]


class ExceptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many_for_timecard(
        self,
        *,
        timecard_id: UUID,
        entries: Sequence[ExceptionCreateEntry],
    ) -> list[TimecardException]:
        exceptions = [
            TimecardException(
                timecard_id=timecard_id,
                severity=severity,
                exception_type=exception_type,
                reason=reason,
                resolved=False,
            )
            for severity, exception_type, reason in entries
        ]
        if not exceptions:
            return []

        self._session.add_all(exceptions)
        await self._session.flush()
        for exception in exceptions:
            await self._session.refresh(exception)
        return exceptions

    async def resolve_exceptions(
        self,
        exceptions: Iterable[TimecardException],
    ) -> None:
        resolved_at = datetime.now(UTC)
        for exception in exceptions:
            exception.resolved = True
            exception.resolved_at = resolved_at
        await self._session.flush()
        for exception in exceptions:
            await self._session.refresh(exception)
