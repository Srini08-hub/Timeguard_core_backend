import mimetypes

from fastapi import APIRouter, HTTPException, Response, status

from src.utils.storage import get_attachment_bytes

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.get("/{path:path}", status_code=status.HTTP_200_OK)
async def get_attachment(path: str) -> Response:
    try:
        data = get_attachment_bytes(path)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        ) from exc

    media_type, _ = mimetypes.guess_type(path)
    return Response(content=data, media_type=media_type or "application/octet-stream")
