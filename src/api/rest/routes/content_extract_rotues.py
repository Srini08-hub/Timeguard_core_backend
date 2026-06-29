from fastapi import APIRouter, Depends, Path, status

from src.api.rest.dependency.services import get_content_extract_service
from src.core.services.content_extract_service import ContentExtractService

router = APIRouter(prefix="/content-extracts", tags=["content-extracts"])


@router.get(
    "/email/{email_id}",
    status_code=status.HTTP_200_OK,
)
async def get_content_extracts_by_email_id(
    email_id: str = Path(description="The ID of the email to fetch content extracts for"),
    content_extract_service: ContentExtractService = Depends(get_content_extract_service),
) -> list[dict]:
    import uuid

    email_uuid = uuid.UUID(email_id)
    response = await content_extract_service.get_content_extracts_by_email_id(email_uuid)
    return response
