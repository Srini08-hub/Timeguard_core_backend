import uuid

from src.core.exceptions.custom_exception import (
    ConflictException,
    DatabaseException,
    ResourceNotFound,
)
from src.data.models.assignments import AssignmentStatus
from src.data.models.clients import Client
from src.data.repositories.assignment_repository import AssignmentRepository
from src.data.repositories.client_repository import ClientRepository
from src.data.repositories.department_repository import DepartmentRepository
from src.data.repositories.employee_repository import EmployeeRepository
from src.schemas.client_schema import ClientCreate, ClientResponse, ClientUpdate


class ClientService:
    def __init__(
        self,
        client_repository: ClientRepository,
        department_repository: DepartmentRepository,
        assignment_repository: AssignmentRepository,
        employee_repository: EmployeeRepository,
    ) -> None:
        self._client_repository = client_repository
        self._department_repository = department_repository
        self._assignment_repository = assignment_repository
        self._employee_repository = employee_repository

    async def create_client(self, payload: ClientCreate) -> ClientResponse:
        existing_client = await self._client_repository.get_by_sender_email(
            payload.sender_email
        )
        if existing_client:
            raise ConflictException("Client with this email already exists")

        try:
            client = await self._client_repository.create(
                client_name=payload.client_name,
                sender_email=payload.sender_email,
                sender_domain=payload.sender_domain,
                created_by=payload.created_by,
            )
        except Exception as exc:
            raise DatabaseException("Failed to create client") from exc

        return self._to_response(client)

    async def get_active_clients(self) -> list[ClientResponse]:
        try:
            clients = await self._client_repository.get_active_clients()
        except Exception as exc:
            raise DatabaseException("Failed to retrieve active clients") from exc

        return [self._to_response(client) for client in clients]

    async def update_client(
        self, client_id: uuid.UUID, payload: ClientUpdate
    ) -> ClientResponse:
        try:
            client = await self._client_repository.update(
                client_id=client_id,
                client_name=payload.client_name,
                sender_email=payload.sender_email,
                sender_domain=payload.sender_domain,
                # is_active=payload.is_active,
            )
        except Exception as exc:
            raise DatabaseException("Failed to update client") from exc

        if not client:
            raise ResourceNotFound(f"Client with id {client_id} not found")

        return self._to_response(client)

    async def soft_delete_client(self, client_id: uuid.UUID) -> None:
        try:
            # Get all assignments for this client
            assignments = await self._assignment_repository.get_by_client(client_id)

            # Update all assignment statuses to inactive
            await self._assignment_repository.update_by_client(
                client_id, status=AssignmentStatus.INACTIVE
            )

            # Update employees is_assigned to false
            for assignment in assignments:
                await self._employee_repository.update_assignment(assignment.emp_id, False)

            # Soft delete all departments for this client
            await self._department_repository.soft_delete_by_client(client_id)

            # Soft delete the client
            deleted = await self._client_repository.soft_delete(client_id)
        except Exception as exc:
            raise DatabaseException("Failed to delete client") from exc

        if not deleted:
            raise ResourceNotFound(f"Client with id {client_id} not found")

    def _to_response(self, client: Client) -> ClientResponse:
        return ClientResponse(
            client_id=client.client_id,
            client_name=client.client_name,
            sender_email=client.sender_email,
            sender_domain=client.sender_domain,
            is_active=client.is_active,
            created_at=client.created_at,
        )
