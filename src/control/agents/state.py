from typing import Literal, NotRequired, TypedDict
from uuid import UUID

# from sqlalchemy.dialects.postgresql import UUID


class AttachmentState(TypedDict):
    gmail_attachment_id: str
    file_name: str
    # mime_type: str
    # file_size: int
    doc_type: NotRequired[str]
    attachment_url: NotRequired[str]
    attachment_db_id: NotRequired[UUID]
    # is_timesheet: NotRequired[bool]
    # confidence: NotRequired[float]
    # reasoning: NotRequired[str]
    status: str
    # extraction_id: NotRequired[UUID]
    # raw_json: NotRequired[list]
    # error: NotRequired[str]
    # retry_count: NotRequired[int]


class TimeguardState(TypedDict):
    email_id: NotRequired[UUID]
    gmail_message_id: str
    attachment_ids: NotRequired[list[UUID]]
    sender_mail: NotRequired[str]
    body: NotRequired[str]
    attachments: NotRequired[list[AttachmentState]]
    current_attachment_index: NotRequired[int]
    pdf_classification: NotRequired[str]

    error: NotRequired[str]


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
    pdf_reason: NotRequired[str]
    # status:             NotRequired[str]   # "processing" | "classified" | "uncertain"


class ExcelClassifierState(TypedDict):
    file_path: str
    sheet_names: NotRequired[list[str]]  # all sheet names in workbook
    sheet_queue: NotRequired[list[int]]  # indices yet to process
    current_sheet: NotRequired[dict | None]  # sheet being worked on
    anchor_hits: NotRequired[list[dict]]  # {keyword, score, position}
    context_snippet: NotRequired[str]  # harvested rows around anchor
    llm_response: NotRequired[str]
    excel_classification: NotRequired[
        Literal["PENDING", "TIMESHEET", "NOT_A_TIMESHEET"]
    ]
    confidence: NotRequired[str]
    reason: NotRequired[str]
    sheets_checked: NotRequired[int]
