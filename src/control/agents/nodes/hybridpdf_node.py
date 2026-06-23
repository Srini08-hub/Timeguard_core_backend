# import logging
# from pathlib import Path
# from urllib.parse import urlparse

# from langchain_core.runnables import RunnableConfig
# from llama_cloud import AsyncLlamaCloud

# from src.config.settings import settings
# from src.control.agents.graph_config import get_db_session
# from src.control.agents.state import AttachmentState, TimeguardState
# from src.data.models.attachment import AttachmentStatus
# from src.data.repositories.attachment_repository import AttachmentRepository

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)


# def _current_attachment(state: TimeguardState) -> AttachmentState:
#     attachments = state.get("attachments", [])
#     index = state.get("current_attachment_index", 0)

#     if index >= len(attachments):
#         raise ValueError("No attachment available for PDF processing")

#     return attachments[index]


# def _resolve_attachment_path(attachment: AttachmentState) -> Path:
#     attachment_url = attachment.get("attachment_url")
#     if attachment_url:
#         parsed_url = urlparse(attachment_url)
#         candidate = settings.ATTACHMENT_STORAGE_DIR / Path(parsed_url.path).name
#         if candidate.exists():
#             return candidate

#     file_name = attachment.get("file_name")
#     if file_name:
#         matches = list(settings.ATTACHMENT_STORAGE_DIR.glob(f"*_{file_name}"))
#         if matches:
#             return matches[0]

#     raise FileNotFoundError(
#         f"Unable to resolve a stored file for attachment "
#         f"{attachment.get('file_name', '')}"
#     )


# def _attachment_status_from_classification(
#     classification: str | None,
# ) -> AttachmentStatus:
#     if classification == "TIMESHEET":
#         return AttachmentStatus.TIMESHEET

#     return AttachmentStatus.NOT_TIMESHEET


# def _classification_rules() -> list[dict[str, str]]:
#     return [
#         {
#             "type": "TIMESHEET",
#             "description": (
#                 "Documents that are timesheets, time cards, work logs, or attendance "
#                 "sheets. They usually contain employee names or IDs, dates or pay "
#                 "periods, days of the week, clock in/out times, hours worked, total "
#                 "hours, project or client rows, approvals, or signatures."
#             ),
#         },
#         {
#             "type": "NOT_TIMESHEET",
#             "description": (
#                 "Documents that are not timesheets, including invoices, receipts, "
#                 "contracts, emails, cover sheets, memos, or other files without "
#                 "explicit time tracking records."
#             ),
#         },
#     ]


# def _result_value(result: object, key: str) -> str | float | None:
#     if result is None:
#         return None

#     if isinstance(result, dict):
#         value = result.get(key)
#         return value if isinstance(value, (str, float, int)) else None

#     value = getattr(result, key, None)
#     return value if isinstance(value, (str, float, int)) else None


# async def _classify_with_llamacloud(
#     pdf_path: Path,
# ) -> tuple[str | None, float | None, str | None]:
#     client = AsyncLlamaCloud(api_key=settings.LLAMA_CLOUD_API_KEY)
#     file_obj = await client.files.create(file=str(pdf_path), purpose="classify")
#     result = await client.classifier.classify(
#         file_ids=[file_obj.id],
#         rules=_classification_rules(),
#         mode="MULTIMODAL",
#     )

#     if not getattr(result, "items", None):
#         raise ValueError(
#             f"LlamaClassify returned no classification results for {pdf_path}"
#         )

#     item = result.items[0]
#     classified = getattr(item, "result", None)
#     classification = _result_value(classified, "type")
#     confidence = _result_value(classified, "confidence")
#     reasoning = _result_value(classified, "reasoning")

#     return classification, confidence, reasoning


# async def hybridpdfnode(
#     state: TimeguardState,
#     config: RunnableConfig,
# ) -> TimeguardState:
#     # db_session = get_db_session(config)
#     # attachment_repository = AttachmentRepository(db_session)

#     # attachment_state = _current_attachment(state)
#     # pdf_path = _resolve_attachment_path(attachment_state)

#     # logger.info(
#     #     "Processing digital PDF attachment %s from %s",
#     #     attachment_state.get("file_name", ""),
#     #     pdf_path,
#     # )

#     # # classification, confidence, reasoning =
# await _classify_with_llamacloud(pdf_path)
#     # # attachment_status = _attachment_status_from_classification(classification)

#     # # logger.info(
#     # #     "LlamaClassify labeled attachment %s as %s (confidence=%s, reasoning=%s)",
#     # #     attachment_state.get("file_name", ""),
#     # #     classification,
#     # #     confidence,
#     # #     reasoning,
#     # # )

#     # attachment_db_id = attachment_state.get("attachment_db_id")
#     # if attachment_db_id:
#     #     attachment = await attachment_repository.get_by_id(attachment_db_id)
#     #     if attachment is not None:
#     #         await attachment_repository.set_status(
#     #             attachment,
#     #             status=attachment_status,
#     #         )
#     #         await db_session.commit()
#     #         logger.info(
#     #             "Updated attachment %s to status %s",
#     #             attachment_db_id,
#     #             attachment_status,
#     #         )
#     #     else:
#     #         logger.warning(
#     #             "Attachment %s not found for status update", attachment_db_id
#     #         )

#     # current_index = state.get("current_attachment_index", 0)
#     # attachments = list(state.get("attachments", []))
#     # attachments[current_index] = {
#     #     **attachment_state,
#     #     "is_timesheet": classification == "TIMESHEET",
#     # }
#     return {
#         **state,
#         # "attachments": attachments,
#     }
from src.control.agents.state import TimeguardState


async def hybridpdfnode(
    state: TimeguardState,
) -> TimeguardState:
    return {
        **state,
    }
