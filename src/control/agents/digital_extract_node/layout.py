"""
Phase 2 · Create unified layout elements.

This is the step your original algorithm named but didn't specify, and
it's the one with a real, silent failure mode: pdfplumber tables and
PyMuPDF text blocks both describe the SAME region of the page
independently. Verified directly against a synthetic test PDF — every
text block inside a detected table's bbox is a duplicate of a cell
pdfplumber already parsed. Naively concatenating both extractions
double-emits every table row.

The fix: for each page, build the table elements first, then keep ONLY
the text blocks whose bbox does NOT substantially overlap any table's
bbox. "Substantially" uses an IoU-style area-overlap-ratio threshold
rather than exact containment, since a heading block sitting just above
a table can have a bbox that brushes the table's top edge without
actually being table content.

Fallback path: some "digital" timesheets render a grid using whitespace
alignment only (no ruling lines), which pdfplumber's line-based table
finder won't detect at all. When a page has zero detected tables but
its surviving text blocks look row-aligned (multiple blocks sharing a
y-band, repeating across several y-bands — the signature of a table
with no borders), we reconstruct a virtual table from text-block
geometry instead of leaving it as disconnected text fragments.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.control.agents.digital_extract_node.raw_extract import (
    PageRaw,
    TableBlock,
    TextBlock,
)

OVERLAP_THRESHOLD = 0.5  # a text block this overlapped by a table bbox is suppressed


class ElementKind(StrEnum):
    TEXT = "text"
    TABLE = "table"


@dataclass
class LayoutElement:
    page_num: int
    bbox: tuple[float, float, float, float]
    kind: str
    text: str | None = None
    rows: list[list[str]] | None = None


def _bbox_overlap_ratio(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    """Fraction of bbox `a`'s area that's covered by bbox `b`."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    intersection = (ix1 - ix0) * (iy1 - iy0)
    a_area = max((ax1 - ax0) * (ay1 - ay0), 1e-6)
    return_value: float = intersection / a_area
    return return_value


def _suppress_table_covered_text(
    text_blocks: list[TextBlock], tables: list[TableBlock]
) -> list[TextBlock]:
    kept = []
    for tb in text_blocks:
        covered = any(
            _bbox_overlap_ratio(tb.bbox, t.bbox) >= OVERLAP_THRESHOLD for t in tables
        )
        if not covered:
            kept.append(tb)
    return kept


def _group_into_y_bands(
    text_blocks: list[TextBlock], y_tolerance: float = 4.0
) -> list[list[TextBlock]]:
    """Groups text blocks into bands sharing a similar y0 (i.e. same visual row)."""
    sorted_blocks = sorted(text_blocks, key=lambda b: b.bbox[1])
    bands: list[list[TextBlock]] = []
    for tb in sorted_blocks:
        placed = False
        for band in bands:
            if abs(band[0].bbox[1] - tb.bbox[1]) <= y_tolerance:
                band.append(tb)
                placed = True
                break
        if not placed:
            bands.append([tb])
    return bands


def _looks_row_aligned(
    text_blocks: list[TextBlock], min_bands: int = 2, min_per_band: int = 2
) -> bool:
    """
    Heuristic fallback trigger: do these surviving text blocks look like
    an unruled (borderless) table? True if there are at least
    `min_bands` distinct y-bands, each containing at least
    `min_per_band` blocks at different x positions — i.e. several rows,
    each with several columns, lined up by whitespace alone rather than
    ruling lines.
    """
    bands = _group_into_y_bands(text_blocks)
    qualifying = [b for b in bands if len(b) >= min_per_band]
    return len(qualifying) >= min_bands


def _reconstruct_virtual_table(
    text_blocks: list[TextBlock], min_cols: int = 2
) -> tuple[TableBlock, list[TextBlock]] | None:
    """
    Builds a synthetic TableBlock from row-aligned text blocks when no
    real (ruled) table was detected. Each y-band with at least
    `min_cols` blocks becomes one row; within a band, blocks are
    ordered left-to-right by x0. Bands with fewer than `min_cols`
    blocks (e.g. a single "Employee: Sam Borderless" heading line sitting
    above the grid) are excluded from the table and left as ordinary
    surrounding text — only genuinely multi-column bands get folded in,
    so a normal heading line never gets misread as a 1-cell table row.

    Returns (table, consumed_blocks) so the caller can remove EXACTLY
    the blocks that became table cells from the surrounding-text list,
    rather than relying on a bbox-overlap heuristic that could
    accidentally also swallow a heading line whose bbox happens to sit
    inside the reconstructed table's bounding rectangle.
    """
    bands = _group_into_y_bands(text_blocks)
    table_bands = [b for b in bands if len(b) >= min_cols]
    if len(table_bands) < 2:
        return None

    table_bands.sort(key=lambda band: band[0].bbox[1])
    rows = []
    consumed: list[TextBlock] = []
    for band in table_bands:
        band_sorted = sorted(band, key=lambda b: b.bbox[0])
        rows.append([b.text.replace("\n", " ") for b in band_sorted])
        consumed.extend(band_sorted)

    all_x0 = [t.bbox[0] for t in consumed]
    all_x1 = [t.bbox[2] for t in consumed]
    all_y0 = [t.bbox[1] for t in consumed]
    all_y1 = [t.bbox[3] for t in consumed]
    bbox = (min(all_x0), min(all_y0), max(all_x1), max(all_y1))
    page_num = text_blocks[0].page_num
    return TableBlock(page_num=page_num, bbox=bbox, rows=rows), consumed


def unify_page(page: PageRaw) -> list[LayoutElement]:
    """
    Phase 2 entry point for one page. Returns a flat list of
    LayoutElement (text + table), deduplicated, in no particular order
    yet (Phase 3 — sort_elements — handles ordering).
    """
    elements: list[LayoutElement] = []

    for t in page.tables:
        elements.append(
            LayoutElement(
                page_num=page.page_num, bbox=t.bbox, kind=ElementKind.TABLE, rows=t.rows
            )
        )

    surviving_text = _suppress_table_covered_text(page.text_blocks, page.tables)

    if not page.tables and surviving_text and _looks_row_aligned(surviving_text):
        reconstruction = _reconstruct_virtual_table(surviving_text)
        if reconstruction is not None:
            virtual_table, consumed_blocks = reconstruction
            elements.append(
                LayoutElement(
                    page_num=page.page_num,
                    bbox=virtual_table.bbox,
                    kind=ElementKind.TABLE,
                    rows=virtual_table.rows,
                )
            )
            consumed_ids = {id(b) for b in consumed_blocks}
            surviving_text = [tb for tb in surviving_text if id(tb) not in consumed_ids]

    for tb in surviving_text:
        elements.append(
            LayoutElement(
                page_num=page.page_num,
                bbox=tb.bbox,
                kind=ElementKind.TEXT,
                text=tb.text,
            )
        )

    return elements
