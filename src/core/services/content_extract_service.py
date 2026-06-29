import logging
from typing import Any
from uuid import UUID

from src.data.repositories.content_extract_repository import ContentExtractRepository

logger = logging.getLogger(__name__)


class ContentExtractService:
    def __init__(self, content_extract_repository: ContentExtractRepository) -> None:
        self.content_extract_repository = content_extract_repository

    async def get_content_extracts_by_email_id(self, email_id: UUID) -> list[dict[str, Any]]:
        """Get all content extracts for an email with attachment names.

        Args:
            email_id: The email ID to query

        Returns:
            List of dictionaries with content extract data including attachment name
        """
        return await self.content_extract_repository.get_extracted_data_for_merge(
            email_id=email_id
        )
