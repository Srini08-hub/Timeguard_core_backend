from __future__ import annotations

from typing import Annotated, Literal, NotRequired, TypedDict
from uuid import UUID

from src.control.agents.digital_extract_node.serialize import SerialisedPdfBlock
from src.control.agents.excel_extract_node.probe_extract import SerialisedBlock


# from sqlalchemy.dialects.postgresql import UUID
def _merge_results(
    left: list[BlockResult], right: list[BlockResult]
) -> list[BlockResult]:
    return left + right


class BlockResult(TypedDict):
    sheet_name: str
    block_index: int
    success: bool
    extraction: dict | None  # Parsed JSON object if success
    error: str | None  # error message if not success
    raw_response_on_failure: str | None


class AttachmentState(TypedDict):
    gmail_attachment_id: NotRequired[str]
    file_name: str
    # mime_type: str
    # file_size: int
    doc_type: NotRequired[str]
    attachment_url: NotRequired[str]
    attachment_db_id: NotRequired[UUID]
    is_timesheet: NotRequired[bool]
    timesheet_id: NotRequired[UUID]
    # confidence: NotRequired[float]
    # reasoning: NotRequired[str]
    status: str
    # extraction_id: NotRequired[UUID]
    # raw_json: NotRequired[list]
    # error: NotRequired[str]
    # retry_count: NotRequired[int]


class TimeguardState(TypedDict):
    email_id: NotRequired[UUID]
    email_body_timesheet_id: NotRequired[UUID]
    gmail_message_id: str
    attachment_ids: NotRequired[list[UUID]]
    sender_mail: NotRequired[str]
    body: NotRequired[str]
    subject: NotRequired[str]
    attachments: NotRequired[list[AttachmentState]]
    current_attachment_index: NotRequired[int]
    error: NotRequired[str]
    email_body_anchor_hits: NotRequired[list[dict]]
    email_body_context: NotRequired[str]
    email_body_classification: NotRequired[Literal["TIMESHEET", "NOT_A_TIMESHEET"]]
    # email_body_extraction_done: NotRequired[bool]
    is_timesheet: NotRequired[bool]

    # sheet_name: Optional[str]            # restrict to one sheet, or None for all

    # Excel
    blocks: list[SerialisedBlock]  # used
    current_excel_block_index: int  # usedd
    results: Annotated[list[BlockResult], _merge_results]
    # block: SerialisedBlock

    d_blocks: list[SerialisedPdfBlock]
    # results: Annotated[List[BlockResult], _merge_results]


# class BlockTaskState(TypedDict):
#     block: SerialisedBlock


class PDFClassifierState(TypedDict):
    # ── input ────────────────────────────────────────────────────────────────
    pdf_path: str

    # ── control ──────────────────────────────────────────────────────────────
    page_queue: NotRequired[list[int]]
    pages_checked: NotRequired[int]

    # ── per-page working data (overwritten each iteration) ───────────────────
    current_page: NotRequired[dict | None]
    anchor_hits: NotRequired[list[dict]]
    context_snippet: NotRequired[str]

    # ── output ───────────────────────────────────────────────────────────────
    pdf_classification: NotRequired[str]  # "TIMESHEET" | "NOT_A_TIMESHEET"


class ExcelClassifierState(TypedDict):
    file_path: str
    sheet_names: NotRequired[list[str]]  # all sheet names in workbook
    sheet_queue: NotRequired[list[int]]  # indices yet to process
    current_sheet: NotRequired[dict | None]  # sheet being worked on
    anchor_hits: NotRequired[list[dict]]  # {keyword, score, position}
    context_snippet: NotRequired[str]  # harvested rows around anchor
    excel_classification: NotRequired[
        Literal["TIMESHEET", "NOT_A_TIMESHEET", "PENDING"]
    ]
    # confidence: NotRequired[str]
    # reason: NotRequired[str]
    # sheets_checked: NotRequired[int]


class ScannedPDFClassifierState(TypedDict):
    pdf_path: str
    page_queue: NotRequired[list[int]]
    pages_checked: NotRequired[int]
    current_page: NotRequired[dict | None]
    scanned_pdf_classification: NotRequired[Literal["TIMESHEET", "NOT_A_TIMESHEET"]]
    # final_status: NotRequired[Literal["TIMESHEET", "NOT_A_TIMESHEET"]]
    confidence: NotRequired[float]
    reason: NotRequired[str]


class ImageClassifierState(TypedDict):
    # ── input ────────────────────────────────────────────────────────────────
    image_path: str  # local path to downloaded image

    # ── working data ─────────────────────────────────────────────────────────
    # image_base64:          NotRequired[str]    # base64 encoded image
    image_media_type: NotRequired[str]  # "image/jpeg" | "image/png" etc.

    # ── output ───────────────────────────────────────────────────────────────
    image_classification: NotRequired[str]  # TIMESHEET | NOT_A_TIMESHEET | UNCERTAIN
    image_reason: NotRequired[str]
