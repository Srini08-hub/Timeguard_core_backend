from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

import fitz
import pdfplumber

from src.control.agents.state import TimeguardState
from src.utils.storage import resolve_attachment_to_local_path

logger = logging.getLogger(__name__)


def classify_page(text: str, images: list, page_area: float) -> str:
    word_count = len(text.split())
    has_real_text = word_count > 10

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


def pdf_classifying_node(state: TimeguardState) -> TimeguardState:
    index = state.get("current_attachment_index", 0)
    attachments = state.get("attachments", [])
    pdf_path = resolve_attachment_to_local_path(attachments[index])
    classification = classify_pdf(pdf_path)

    attachments[index] = {
        **attachments[index],
        "doc_type": classification,
        "file_path": pdf_path,
    }
    logger.info(
        "Classified attachment %s (%s) as %s",
        attachments[index].get("file_name", ""),
        pdf_path,
        classification,
    )

    result = cast(
        TimeguardState,
        {
            **state,
            "attachments": attachments,
            "pdf_file_path": str(pdf_path),
        },
    )

    if classification == "scanned_pdf":
        result["scanned_pdf_file_path"] = str(pdf_path)

    return result


def route_pdf_classification(state: TimeguardState) -> str:
    index = state.get("current_attachment_index", 0)
    attachments = state.get("attachments", [])
    classification = attachments[index].get("doc_type")
    if classification == "digital_pdf":
        return "pdf_node"
    if classification == "scanned_pdf":
        return "scanned_pdf_node"
    if classification == "hybrid_pdf":
        return "hybrid_pdf_node"

    return "increment_attachment_node"
