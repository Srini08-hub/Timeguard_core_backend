"""Render scanned PDF pages to PNG images for vision LLM extraction."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import fitz

RENDER_ZOOM = 2
IMAGE_MEDIA_TYPE = "image/png"


@dataclass(frozen=True)
class RenderedPdfPage:
    page_number: int
    media_type: str
    image_base64: str


def render_pdf_pages(pdf_path: Path) -> list[RenderedPdfPage]:
    """Convert every page of a PDF to a base64-encoded PNG image."""
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF path does not exist: {pdf_path}")

    doc = fitz.open(pdf_path)
    pages: list[RenderedPdfPage] = []
    try:
        matrix = fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image_base64 = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
            pages.append(
                RenderedPdfPage(
                    page_number=page_index + 1,
                    media_type=IMAGE_MEDIA_TYPE,
                    image_base64=image_base64,
                )
            )
    finally:
        doc.close()

    return pages
