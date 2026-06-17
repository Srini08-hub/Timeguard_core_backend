import logging
from pathlib import Path
from uuid import uuid4

from src.config.settings import settings

logger = logging.getLogger(__name__)


def save_attachment(data: bytes, filename: str) -> tuple[str, Path]:
    """
    Persist attachment bytes to the local filesystem.

    Returns:
        (public_url, absolute_path)
    """
    storage_dir: Path = settings.ATTACHMENT_STORAGE_DIR
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Use a UUID prefix to avoid filename collisions
    safe_filename = f"{uuid4().hex}_{filename}"
    file_path = storage_dir / safe_filename

    file_path.write_bytes(data)
    logger.info("Saved attachment to %s", file_path)

    public_url = f"{settings.ATTACHMENT_BASE_URL.rstrip('/')}/{safe_filename}"
    return public_url, file_path
