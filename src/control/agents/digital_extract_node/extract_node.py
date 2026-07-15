"""
Part A orchestrator for the PDF pipeline.

Chains: raw_extract (Phase 1) -> unify_page (Phase 2, per page) ->
sort_elements (Phase 3, per page) -> serialise_all (markdown).
Everything stays at the PDF-document level so one PDF becomes one
markdown block for the LLM.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.control.agents.digital_extract_node.layout import unify_page
from src.control.agents.digital_extract_node.raw_extract import extract_raw
from src.control.agents.digital_extract_node.serialize import (
    SerialisedPdfBlock,
    serialise_all,
)
from src.control.agents.digital_extract_node.sort_elements import sort_elements

if TYPE_CHECKING:
    from src.control.agents.state import AttachmentState, TimeguardState
from src.utils.storage import resolve_attachment_to_local_path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pdf_timesheet_extractor")


def extract_pdf(pdf_path: str) -> list[SerialisedPdfBlock]:
    pages = extract_raw(pdf_path)

    all_pages_ordered = []
    for page in pages:
        elements = unify_page(page)
        ordered = sort_elements(elements, page.width)
        all_pages_ordered.append(ordered)

    c = serialise_all(all_pages_ordered)
    # write_markdown(c, Path(pdf_path).with_suffix(".md"))
    logger.info(c)
    return c


# def write_markdown(blocks: list[SerialisedPdfBlock], output_path: Path) -> None:
#     with open(output_path, "w", encoding="utf-8") as f:
#         for i, block in enumerate(blocks):
#             f.write(block.text_payload)

#             if i < len(blocks) - 1:
#                 f.write("\n\n---\n\n")


def _current_attachment(state: TimeguardState) -> AttachmentState:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    if index >= len(attachments):
        raise ValueError("No attachment available for PDF processing")

    return attachments[index]


# def _resolve_attachment_path(attachment: AttachmentState) -> Path | None:
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
#     return None


def digital_pdf_extraction_node(state: TimeguardState) -> dict:
    """Part A entry point: PyMuPDF+pdfplumber extraction -> one PDF markdown block."""
    attachment = _current_attachment(state)
    # file_path = _resolve_attachment_path(attachment)
    file_path = resolve_attachment_to_local_path(attachment)
    if file_path is None:
        raise ValueError("Could not resolve attachment path for PDF extraction")
    blocks = extract_pdf(str(file_path))
    logger.info("Probed PDF '%s': found %d PDF block(s).", file_path, len(blocks))
    logger.info(blocks)
    return {"d_blocks": blocks}
