"""
Markdown serialisation.

Converts the ordered PDF page stream into one compact markdown payload
for the whole document. Each page gets its own heading, followed by the
page's text and tables in reading order, so Part B receives one
self-contained block per PDF instead of one block per employee.

Markdown tables are a deliberately compact format for LLM consumption —
denser than the "Record N: key: value" block style used for Excel,
appropriate here because PDF tables are typically narrower (a handful
of day/hour columns) and markdown's pipe-table syntax is something the
model has seen at huge scale in training, which tends to help adherence
to the implied row/column structure on the first attempt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.control.agents.digital_extract_node.layout import ElementKind, LayoutElement

# from layout import LayoutElement


@dataclass
class SerialisedPdfBlock:
    block_index: int
    n_pages: int
    text_payload: str


def _clean_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("\n", " ")
    text = text.replace("|", "/")
    return text


def _table_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    header = rows[0]
    body = rows[1:]
    lines = []
    lines.append("| " + " | ".join(_clean_cell(c) for c in header) + " |")
    lines.append("|" + "|".join(" --- " for _ in header) + "|")
    for row in body:
        padded = (row + [""] * len(header))[: len(header)]
        lines.append("| " + " | ".join(_clean_cell(c) for c in padded) + " |")
    return "\n".join(lines)


def _render_page_elements(page_elements: list[LayoutElement]) -> list[str]:
    lines: list[str] = []
    for e in page_elements:
        if e.kind == ElementKind.TABLE:
            if e.rows:
                lines.append(_table_to_markdown(e.rows))
                lines.append("")
        elif e.kind == ElementKind.TEXT and e.text:
            lines.append(e.text)
    return lines


def serialise_document(
    all_pages_ordered: list[list[LayoutElement]],
) -> SerialisedPdfBlock:
    lines: list[str] = []
    for page_index, page_elements in enumerate(all_pages_ordered, start=1):
        lines.append(f"## Page {page_index}")
        lines.append("")
        lines.extend(_render_page_elements(page_elements))
        lines.append("")

    payload = f"<!-- block: 0 | type: pdf | pages: {len(all_pages_ordered)} -->\n"
    payload += "\n".join(lines).rstrip() + "\n"

    return SerialisedPdfBlock(
        block_index=0,
        n_pages=len(all_pages_ordered),
        text_payload=payload,
    )


def serialise_all(
    all_pages_ordered: list[list[LayoutElement]],
) -> list[SerialisedPdfBlock]:
    return [serialise_document(all_pages_ordered)]
