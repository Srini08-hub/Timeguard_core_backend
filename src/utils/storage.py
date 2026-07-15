import logging
import mimetypes
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse
from uuid import uuid4

from src.config.settings import settings

logger = logging.getLogger(__name__)


def _using_gcs() -> bool:
    return bool(settings.GCS_BUCKET_NAME)


def _get_bucket() -> Any:
    if not settings.GCS_BUCKET_NAME:
        raise RuntimeError("GCS_BUCKET_NAME is required when using Cloud Storage")

    from google.cloud import storage as gcs_storage

    return gcs_storage.Client().bucket(settings.GCS_BUCKET_NAME)


def _prefixed_object_name(filename: str) -> str:
    prefix = settings.GCS_ATTACHMENT_PREFIX.strip("/")
    safe_filename = f"{uuid4().hex}_{Path(filename).name}"
    if not prefix:
        return safe_filename
    return f"{prefix}/{safe_filename}"


def _public_attachment_url(object_name: str) -> str:
    quoted_object_name = quote(object_name, safe="/")
    return f"{settings.ATTACHMENT_BASE_URL.rstrip('/')}/{quoted_object_name}"


def object_name_from_attachment_url(attachment_url: str) -> str:
    parsed_url = urlparse(attachment_url)
    path = unquote(parsed_url.path).lstrip("/")

    base_path = urlparse(settings.ATTACHMENT_BASE_URL).path.strip("/")
    if base_path and path.startswith(f"{base_path}/"):
        return path[len(base_path) + 1 :]

    return path


def _local_temp_path(object_name: str) -> Path:
    path = settings.LOCAL_ATTACHMENT_TMP_DIR / object_name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_attachment(data: bytes, filename: str) -> tuple[str, Path]:
    """
    Persist attachment bytes and return the gateway URL plus a local processing path.

    In Cloud Run, set GCS_BUCKET_NAME to store durable objects in Cloud Storage.
    For local development without GCS_BUCKET_NAME, this falls back to the previous
    filesystem-backed behavior.
    """
    if _using_gcs():
        object_name = _prefixed_object_name(filename)
        content_type, _ = mimetypes.guess_type(filename)
        blob = _get_bucket().blob(object_name)
        blob.upload_from_string(data, content_type=content_type or "application/octet-stream")

        file_path = _local_temp_path(object_name)
        file_path.write_bytes(data)
        logger.info("Saved attachment to gs://%s/%s", settings.GCS_BUCKET_NAME, object_name)
        return _public_attachment_url(object_name), file_path

    storage_dir: Path = settings.ATTACHMENT_STORAGE_DIR
    storage_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = f"{uuid4().hex}_{Path(filename).name}"
    file_path = storage_dir / safe_filename
    file_path.write_bytes(data)
    logger.info("Saved attachment to %s", file_path)

    public_url = f"{settings.ATTACHMENT_BASE_URL.rstrip('/')}/{quote(safe_filename)}"
    return public_url, file_path


def download_attachment_to_temp(object_name: str) -> Path:
    if not _using_gcs():
        candidate = settings.ATTACHMENT_STORAGE_DIR / Path(object_name).name
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Stored attachment does not exist: {candidate}")

    file_path = _local_temp_path(object_name)
    if file_path.exists():
        return file_path

    blob = _get_bucket().blob(object_name)
    if not blob.exists():
        raise FileNotFoundError(
            f"Cloud Storage attachment does not exist: gs://{settings.GCS_BUCKET_NAME}/{object_name}"
        )
    blob.download_to_filename(str(file_path))
    return file_path


def get_attachment_bytes(object_name: str) -> bytes:
    object_name = unquote(object_name).lstrip("/")

    if _using_gcs():
        blob = _get_bucket().blob(object_name)
        if not blob.exists():
            raise FileNotFoundError(
                f"Cloud Storage attachment does not exist: gs://{settings.GCS_BUCKET_NAME}/{object_name}"
            )
        return bytes(blob.download_as_bytes())

    candidate = settings.ATTACHMENT_STORAGE_DIR / Path(object_name).name
    if not candidate.exists():
        raise FileNotFoundError(f"Stored attachment does not exist: {candidate}")
    return candidate.read_bytes()


def resolve_attachment_to_local_path(attachment: Mapping[str, Any]) -> Path:
    file_path_value = attachment.get("file_path")
    if file_path_value:
        file_path = Path(file_path_value)
        if file_path.exists():
            return file_path

    attachment_url = attachment.get("attachment_url")
    if attachment_url:
        object_name = object_name_from_attachment_url(str(attachment_url))
        return download_attachment_to_temp(object_name)

    file_name = attachment.get("file_name")
    if file_name and not _using_gcs():
        matches = list(settings.ATTACHMENT_STORAGE_DIR.glob(f"*_{file_name}"))
        if matches:
            return matches[0]

    raise FileNotFoundError(
        f"Unable to resolve a stored file for attachment {attachment.get('file_name', '')}"
    )
