from fastapi import APIRouter, Depends, Path, status

from src.api.rest.dependency.services import get_email_service
from src.core.services.email_service import EmailService
from src.schemas.attachment_schema import AttachmentInfo
from src.schemas.email_schema import TimesheetEmailResponse

router = APIRouter()

router = APIRouter(prefix="/emails", tags=["emails"])


@router.get(
    "/timesheet-emails",
    response_model=list[TimesheetEmailResponse],
    status_code=status.HTTP_200_OK,
)
async def get_timesheet_emails(
    EmailService: EmailService = Depends(get_email_service),
) -> list[TimesheetEmailResponse]:
    response = await EmailService.get_timesheet_mail()
    # Implement logic to fetch timesheet emails from the database
    return response


@router.get(
    "/non-timesheet-emails",
    response_model=list[TimesheetEmailResponse],
    status_code=status.HTTP_200_OK,
)
async def get_non_timesheet_emails(
    EmailService: EmailService = Depends(get_email_service),
) -> list[TimesheetEmailResponse]:
    response = await EmailService.get_non_timesheet_mail()
    # Implement logic to fetch non-timesheet emails from the database
    return response


@router.get(
    "/{email_id}/attachments",
    response_model=list[AttachmentInfo],
    status_code=status.HTTP_200_OK,
)
async def get_attachments(
    email_id: str = Path(description="The ID of the email to fetch attachments for"),
    EmailService: EmailService = Depends(get_email_service),
) -> list[AttachmentInfo]:
    response = await EmailService.get_attachments(email_id)
    return response
