from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependency.session import get_async_db
from src.core.services.assignment_service import AssignmentService
from src.core.services.client_rule_service import ClientRuleService
from src.core.services.client_service import ClientService
from src.core.services.content_extract_service import ContentExtractService
from src.core.services.department_service import DepartmentService
from src.core.services.email_service import EmailService
from src.core.services.employee_service import EmployeeService
from src.core.services.timecard_service import TimecardService
from src.core.services.timesheet_service import TimesheetService
from src.data.repositories.assignment_repository import AssignmentRepository
from src.data.repositories.client_repository import ClientRepository
from src.data.repositories.client_rule_repository import ClientRuleRepository
from src.data.repositories.content_extract_repository import ContentExtractRepository
from src.data.repositories.department_repository import DepartmentRepository
from src.data.repositories.email_repository import EmailRepository
from src.data.repositories.employee_repository import EmployeeRepository
from src.data.repositories.exception_repository import ExceptionRepository
from src.data.repositories.timecard_repository import TimecardRepository
from src.data.repositories.timesheet_repository import TimesheetRepository


async def get_email_service(
    db: AsyncSession = Depends(get_async_db),
) -> EmailService:
    return EmailService(EmailRepository(db))


async def get_timesheet_service(
    db: AsyncSession = Depends(get_async_db),
) -> TimesheetService:
    return TimesheetService(TimesheetRepository(db))


async def get_timecard_service(
    db: AsyncSession = Depends(get_async_db),
) -> TimecardService:
    return TimecardService(
        TimecardRepository(db),
        ExceptionRepository(db),
        TimesheetRepository(db),
        EmailRepository(db),
    )


async def get_client_service(
    db: AsyncSession = Depends(get_async_db),
) -> ClientService:
    return ClientService(
        ClientRepository(db),
        DepartmentRepository(db),
        AssignmentRepository(db),
        EmployeeRepository(db),
    )


async def get_client_rule_service(
    db: AsyncSession = Depends(get_async_db),
) -> ClientRuleService:
    return ClientRuleService(
        ClientRuleRepository(db),
        ClientRepository(db),
        DepartmentRepository(db),
    )


async def get_department_service(
    db: AsyncSession = Depends(get_async_db),
) -> DepartmentService:
    return DepartmentService(
        DepartmentRepository(db), AssignmentRepository(db), EmployeeRepository(db)
    )


async def get_employee_service(
    db: AsyncSession = Depends(get_async_db),
) -> EmployeeService:
    return EmployeeService(EmployeeRepository(db), AssignmentRepository(db))


async def get_assignment_service(
    db: AsyncSession = Depends(get_async_db),
) -> AssignmentService:
    return AssignmentService(AssignmentRepository(db), EmployeeRepository(db))


async def get_content_extract_service(
    db: AsyncSession = Depends(get_async_db),
) -> ContentExtractService:
    return ContentExtractService(ContentExtractRepository(db))
