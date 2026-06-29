import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.clients import Client


class ClientRepository:
    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def create(
        self,
        *,
        client_name: str,
        sender_email: str | None = None,
        sender_domain: str | None = None,
        created_by: uuid.UUID | None = None,
    ) -> Client:
        client = Client(
            client_name=client_name,
            sender_email=sender_email,
            sender_domain=sender_domain,
            created_by=created_by,
        )
        self._db_session.add(client)
        await self._db_session.flush()
        return client

    async def get_active_clients(self) -> list[Client]:
        query = select(Client).where(Client.is_active.is_(True))
        result = await self._db_session.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, client_id: uuid.UUID) -> Client | None:
        query = select(Client).where(
            Client.client_id == client_id,
        )
        result = await self._db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_sender_email(self, sender_email: str) -> Client | None:
        query = select(Client).where(
            Client.sender_email == sender_email,
            Client.is_active.is_(True),
        )
        result = await self._db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_sender_domain(self, sender_domain: str) -> Client | None:
        query = select(Client).where(
            Client.sender_domain == sender_domain,
            Client.is_active.is_(True),
        )
        result = await self._db_session.execute(query)
        return result.scalar_one_or_none()

    async def update(
        self,
        client_id: uuid.UUID,
        *,
        client_name: str | None = None,
        sender_email: str | None = None,
        sender_domain: str | None = None,
        is_active: bool | None = None,
    ) -> Client | None:
        client = await self.get_by_id(client_id)
        if not client:
            return None

        if client_name is not None:
            client.client_name = client_name
        if sender_email is not None:
            client.sender_email = sender_email
        if sender_domain is not None:
            client.sender_domain = sender_domain

        await self._db_session.flush()
        return client

    async def soft_delete(self, client_id: uuid.UUID) -> bool:
        client = await self.get_by_id(client_id)
        if not client:
            return False

        client.is_active = False
        await self._db_session.flush()
        return True
