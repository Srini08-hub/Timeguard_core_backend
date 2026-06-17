from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.email_pool_state import EmailPoolState


class EmailPoolStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_mailbox(
        self,
        mailbox_address: str,
    ) -> EmailPoolState | None:
        result = await self.session.execute(
            select(EmailPoolState).where(
                EmailPoolState.mailbox_address == mailbox_address,
            )
        )
        return result.scalar_one_or_none()

    async def update_history_id(
        self,
        mailbox_address: str,
        history_id: str,
    ) -> EmailPoolState:
        state = await self.get_by_mailbox(mailbox_address)

        if state is None:
            state = EmailPoolState(
                mailbox_address=mailbox_address,
                last_history_id=history_id,
            )
            self.session.add(state)
        else:
            state.last_history_id = history_id

        await self.session.flush()
        return state
