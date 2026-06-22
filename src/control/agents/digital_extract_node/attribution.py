"""
Attribution (new step — not in the original algorithm, but required).

A multi-employee timesheet PDF needs every table attributed to a
specific employee BEFORE the LLM ever sees it. Your original pipeline
stopped at "Markdown -> LLM", which would hand the model a flat document
containing N names and N tables and ask it to figure out which goes
with which from position alone. That's exactly the kind of structural
inference work the Excel pipeline deliberately did NOT delegate to the
LLM (merge resolution, layout detection, and header-band construction
were all done deterministically; the LLM only ever filled in a schema
against already-labeled data). The same principle should apply here.

Strategy: walk the page-ordered element stream. Any TEXT element whose
text matches an "employee name" cue (a configurable set of label
patterns: "Employee:", "Name:", "Staff:") becomes the active employee
context. Every TABLE element is attributed to whichever employee
context is currently active. This also carries across page boundaries
(a name block on page 1 stays active into page 2 if no new name block
appears) so a multi-page single-employee timesheet, or a table split
mid-employee across a page break, is not silently mis-attributed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from layout import ElementKind, LayoutElement

NAME_LABEL_PATTERNS = [
    re.compile(r"employee\s*name\s*[:\-]\s*(.+)", re.IGNORECASE),
    re.compile(r"employee\s*[:\-]\s*(.+)", re.IGNORECASE),
    re.compile(r"name\s*[:\-]\s*(.+)", re.IGNORECASE),
    re.compile(r"staff\s*[:\-]\s*(.+)", re.IGNORECASE),
    re.compile(r"worker\s*[:\-]\s*(.+)", re.IGNORECASE),
]


@dataclass
class EmployeeBlock:
    employee_name: str | None
    elements: list[LayoutElement] = field(default_factory=list)


def _extract_name_from_text(text: str) -> str | None:
    for pattern in NAME_LABEL_PATTERNS:
        m = pattern.match(text.strip())
        if m:
            return m.group(1).strip()
    return None


def attribute_to_employees(
    all_pages_ordered: list[list[LayoutElement]],
) -> list[EmployeeBlock]:
    """
    Takes the page-ordered element lists (one list per page, each
    already sorted by sort_elements.sort_elements) and groups them into
    EmployeeBlock units. A new block starts whenever a name-cue text
    element is seen; everything from that point (including the cue line
    itself) until the next name cue belongs to that employee.

    If NO name cue is ever found anywhere in the document, the entire
    document becomes a single EmployeeBlock with employee_name=None —
    this is the single-employee case, and it degrades correctly: nothing
    is dropped, nothing is mis-split.
    """
    blocks: list[EmployeeBlock] = []
    current: EmployeeBlock | None = None
    any_name_found = False

    for page_elements in all_pages_ordered:
        for e in page_elements:
            name = None
            if e.kind == ElementKind.TEXT and e.text:
                name = _extract_name_from_text(e.text)

            if name:
                any_name_found = True
                current = EmployeeBlock(employee_name=name)
                blocks.append(current)
                current.elements.append(e)
            else:
                if current is None:
                    current = EmployeeBlock(employee_name=None)
                    blocks.append(current)
                current.elements.append(e)

    if not any_name_found:
        merged = EmployeeBlock(employee_name=None)
        for b in blocks:
            merged.elements.extend(b.elements)
        return [merged]

    blocks = [
        b
        for b in blocks
        if b.employee_name is not None
        or any(e.kind == ElementKind.TABLE for e in b.elements)
    ]

    return blocks
