from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

import fitz
import pdfplumber

from src.config.settings import settings
from src.control.agents.state import AttachmentState, TimeguardState

logger = logging.getLogger(__name__)


def classify_page(text: str, images: list, page_area: float) -> str:
    word_count = len(text.split())
    has_real_text = word_count >= 10

    has_significant_image = any(
        (img["width"] * img["height"]) >= 0.30 * page_area for img in images
    )

    if has_real_text and not has_significant_image:
        return "digitalpdfnode"
    if has_real_text and has_significant_image:
        return "hybridpdfnode"
    if not has_real_text and has_significant_image:
        return "scannedpdfnode"
    return "blank"


def classify_pdf(path: str | Path) -> str:
    page_types = {
        "digitalpdfnode": 0,
        "hybridpdfnode": 0,
        "scannedpdfnode": 0,
        "blank": 0,
    }

    doc_fitz = fitz.open(str(path))
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page_index, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                page_area = page.width * page.height
                images = doc_fitz[page_index].get_image_info()

                page_type = classify_page(text, images, page_area)
                page_types[page_type] += 1
    finally:
        doc_fitz.close()

    meaningful_total = (
        page_types["digitalpdfnode"]
        + page_types["hybridpdfnode"]
        + page_types["scannedpdfnode"]
    )

    if meaningful_total == 0:
        return "blank_pdf"

    pure_text_ratio = page_types["digitalpdfnode"] / meaningful_total
    hybrid_ratio = page_types["hybridpdfnode"] / meaningful_total
    scanned_ratio = page_types["scannedpdfnode"] / meaningful_total

    if scanned_ratio == 1.0:
        return "scanned_pdf"
    if pure_text_ratio == 1.0:
        return "digital_pdf"
    if hybrid_ratio > 0:
        return "hybrid_pdf"
    return "hybrid_pdf"


def _resolve_attachment_path(attachment: AttachmentState) -> Path:
    attachment_url = attachment.get("attachment_url")
    if attachment_url:
        parsed_url = urlparse(attachment_url)
        candidate = settings.ATTACHMENT_STORAGE_DIR / Path(parsed_url.path).name
        if candidate.exists():
            return candidate

    file_name = attachment.get("file_name")
    if file_name:
        matches = list(settings.ATTACHMENT_STORAGE_DIR.glob(f"*_{file_name}"))
        if matches:
            return matches[0]

    raise FileNotFoundError(
        f"Unable to resolve a stored file for attachment"
        f" {attachment.get('file_name', '')}"
    )


def _current_attachment(state: TimeguardState) -> AttachmentState:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    if index >= len(attachments):
        raise ValueError("No attachment available for PDF classification")

    return attachments[index]


def pdf_classifying_node(state: TimeguardState) -> TimeguardState:
    attachment = _current_attachment(state)
    pdf_path = _resolve_attachment_path(attachment)
    classification = classify_pdf(pdf_path)

    logger.info(
        "Classified attachment %s (%s) as %s",
        attachment.get("file_name", ""),
        pdf_path,
        classification,
    )

    return {
        **state,
        "pdf_classification": classification,
    }


def route_pdf_classification(state: TimeguardState) -> str:
    classification = state.get("pdf_classification")

    if classification == "digital_pdf":
        return "digitalpdfnode"
    if classification == "scanned_pdf":
        return "scannedpdfnode"
    if classification == "hybrid_pdf":
        return "hybridpdfnode"

    return "increment_attachment_node"


# Backwards-compatible alias for existing references.
pdf_node = pdf_classifying_node
