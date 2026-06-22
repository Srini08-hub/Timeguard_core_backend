"""
Phase 1 · Raw extraction.

Pulls two independent views of each page:
  - PyMuPDF "blocks": text fragments with bounding boxes. Fast, accurate
    text geometry, but has no concept of "this is a table."
  - pdfplumber tables: bordered/aligned grids it can detect, with their
    own bounding box and already-parsed row/column cell values.

Both are kept in PDF coordinate space (origin top-left, y increasing
downward for PyMuPDF's "blocks"; pdfplumber uses the same convention)
so they can be reconciled in Phase 2 without a coordinate-system
conversion bug sneaking in.
"""

from __future__ import annotations

from dataclasses import dataclass

import fitz  # PyMuPDF
import pdfplumber


@dataclass
class TextBlock:
    page_num: int  # 0-indexed
    bbox: tuple[float, float, float, float]  # (x0, y0, x1, y1)
    text: str


@dataclass
class TableBlock:
    page_num: int
    bbox: tuple[float, float, float, float]
    rows: list[list[str]]  # already-parsed cell grid from pdfplumber


@dataclass
class PageRaw:
    page_num: int
    width: float
    height: float
    text_blocks: list[TextBlock]
    tables: list[TableBlock]


def _words_to_text_blocks(words: list, page_num: int) -> list[TextBlock]:
    """
    PyMuPDF's get_text("blocks") groups text into whole paragraphs/lines
    by proximity — too coarse to tell a 2-column borderless table apart
    from a single line of prose (verified directly: a "Day  Hours"
    borderless header row comes back as ONE block spanning both
    columns, destroying the column boundary Phase 2's fallback table
    reconstruction depends on).

    Instead we read at word granularity (get_text("words"), which
    already gives PyMuPDF's own (block_no, line_no, word_no) grouping)
    and re-aggregate ourselves: words sharing the same (block_no,
    line_no) become one TextBlock, which keeps prose lines intact while
    preserving every individual word's x-position for column detection
    in layout.py's borderless-table fallback.
    """
    line_groups: dict = {}
    for w in words:
        x0, y0, x1, y1, text, block_no, line_no, word_no = w
        key = (block_no, line_no)
        line_groups.setdefault(key, []).append((x0, y0, x1, y1, text))

    blocks = []
    for _, parts in line_groups.items():
        parts.sort(key=lambda p: p[0])  # left-to-right within the line
        x0 = min(p[0] for p in parts)
        y0 = min(p[1] for p in parts)
        x1 = max(p[2] for p in parts)
        y1 = max(p[3] for p in parts)
        text = " ".join(p[4] for p in parts)
        blocks.append(TextBlock(page_num=page_num, bbox=(x0, y0, x1, y1), text=text))
    return blocks


def extract_raw(pdf_path: str) -> list[PageRaw]:
    """
    Phase 1 entry point. Returns one PageRaw per page, each carrying its
    independently-extracted text blocks and tables — NOT yet merged or
    deduplicated against each other (that's Phase 2, see layout.py).
    """
    pages: list[PageRaw] = []

    doc = fitz.open(pdf_path)
    with pdfplumber.open(pdf_path) as plumber_pdf:
        for page_num in range(len(doc)):
            mupdf_page = doc[page_num]
            plumber_page = plumber_pdf.pages[page_num]

            words = mupdf_page.get_text("words")
            text_blocks = [
                tb for tb in _words_to_text_blocks(words, page_num) if tb.text.strip()
            ]

            found_tables = plumber_page.find_tables()
            tables = []
            for t in found_tables:
                cells = t.extract()
                # Drop tables pdfplumber "found" but couldn't actually
                # populate (e.g. a stray pair of crossing lines with no
                # real cell content) — these are false positives that
                # would otherwise produce an empty, useless table block.
                if cells and any(any(c for c in row) for row in cells):
                    cleaned_cells = [
                        [c if c is not None else "" for c in row] for row in cells
                    ]
                    tables.append(
                        TableBlock(page_num=page_num, bbox=t.bbox, rows=cleaned_cells)
                    )

            pages.append(
                PageRaw(
                    page_num=page_num,
                    width=mupdf_page.rect.width,
                    height=mupdf_page.rect.height,
                    text_blocks=text_blocks,
                    tables=tables,
                )
            )

    doc.close()
    return pages
