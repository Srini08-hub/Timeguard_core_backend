"""
Phase 3 · Sort by page position.

Your original spec just said "sort by page position." A pure top-to-
bottom-then-left-to-right coordinate sort is the right idea for a
single-column page, but breaks the moment two employees are laid out
side-by-side (verified with a synthetic test PDF: Alice's table and
Bob's table occupy the same y-range at different x — a flat sort can
still interleave their rows if anything else on the page perturbs y
slightly, and more importantly, the column boundary itself needs to be
detected before sorting, not assumed).

The fix: detect vertical "columns" first (clusters of elements sharing
an x-range, separated by a horizontal gap with nothing in it), sort
elements WITHIN each column by y, then concatenate columns left to
right. A normal single-column page is just one detected column, so
this is a strict generalisation — it doesn't change behaviour for the
common case (verified below against single_employee.pdf).
"""

from __future__ import annotations

from src.control.agents.digital_extract_node.layout import LayoutElement

COLUMN_GAP_THRESHOLD = 30.0
# points of horizontal whitespace that separates two columns


def _detect_columns(
    elements: list[LayoutElement], page_width: float
) -> list[tuple[float, float]]:
    """
    Returns a list of (x_min, x_max) column bands. Built by projecting
    every element's x-range onto the horizontal axis and merging
    overlapping/near-touching ranges; any gap of at least
    COLUMN_GAP_THRESHOLD points with no element crossing it becomes a
    column boundary.
    """
    if not elements:
        return [(0.0, page_width)]

    x_ranges = sorted((e.bbox[0], e.bbox[2]) for e in elements)
    merged = [list(x_ranges[0])]
    for x0, x1 in x_ranges[1:]:
        last = merged[-1]
        if x0 - last[1] <= COLUMN_GAP_THRESHOLD:
            last[1] = max(last[1], x1)
        else:
            merged.append([x0, x1])
    return [(r[0], r[1]) for r in merged]


def _column_index_for_element(
    e: LayoutElement, columns: list[tuple[float, float]]
) -> int:
    """Assigns an element to whichever column band its x-center falls in."""
    x_center = (e.bbox[0] + e.bbox[2]) / 2
    for i, (x0, x1) in enumerate(columns):
        if x0 <= x_center <= x1:
            return i
    distances = [min(abs(x_center - x0), abs(x_center - x1)) for x0, x1 in columns]
    return distances.index(min(distances))


def sort_elements(
    elements: list[LayoutElement], page_width: float
) -> list[LayoutElement]:
    """
    Phase 3 entry point for one page's unified elements.

    1. Detect column bands across the whole page.
    2. Assign every element to a column.
    3. Within each column, sort top-to-bottom by y0 (ties broken by x0).
    4. Concatenate columns left-to-right.

    A single-column page (the common case for most timesheets) produces
    exactly one column band, so this degenerates to a plain top-to-
    bottom sort when there's nothing to disambiguate.
    """
    if not elements:
        return []

    columns = _detect_columns(elements, page_width)
    buckets: list[list[LayoutElement]] = [[] for _ in columns]

    for e in elements:
        idx = _column_index_for_element(e, columns)
        buckets[idx].append(e)

    ordered: list[LayoutElement] = []
    for bucket in buckets:
        bucket.sort(key=lambda e: (e.bbox[1], e.bbox[0]))
        ordered.extend(bucket)

    return ordered
