from typing import Literal, NotRequired, TypedDict
from uuid import UUID

# from sqlalchemy.dialects.postgresql import UUID


class AttachmentState(TypedDict):
    gmail_attachment_id: NotRequired[str]
    file_name: str
    # mime_type: str
    # file_size: int
    doc_type: NotRequired[str]
    attachment_url: NotRequired[str]
    attachment_db_id: NotRequired[UUID]
    is_timesheet: NotRequired[bool]
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
    error: NotRequired[str]
    email_body_anchor_hits: NotRequired[list[dict]]
    email_body_context: NotRequired[str]
    email_body_classification: NotRequired[Literal["TIMESHEET", "NOT_A_TIMESHEET"]]


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
