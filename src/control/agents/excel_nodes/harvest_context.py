from src.control.agents.state import TimeguardState


def harvest_context(state: TimeguardState) -> TimeguardState:
    """
    For Excel: grab rows surrounding the anchor hit row
    + the full header row (row 0) for column context.
    """
    sheet = state.get("excel_current_sheet")
    if not sheet:
        return state
    # text   = sheet["combined"]
    rows = sheet.get("rows", [])
    hits = state.get("excel_anchor_hits", [])
    chunks = []

    for hit in hits:
        # Find which row index contains the matched keyword
        kw = hit["keyword"].lower()
        matched_row_idx = next(
            (i for i, row in enumerate(rows) if any(kw in str(cell).lower() for cell in row)),
            0,
        )

        # Grab header row + ±5 rows around the match for context
        header = rows[0] if rows else []
        start = max(0, matched_row_idx - 5)
        end = min(len(rows), matched_row_idx + 6)
        context_rows = rows[start:end]

        header_str = " | ".join(header)
        context_str = "\n".join(" | ".join(row) for row in context_rows)

        chunks.append(
            f"[keyword: '{hit['keyword']}' | score: {hit['score']:.0f}%]\n"
            f"Header row: {header_str}\n"
            f"Surrounding rows:\n{context_str}"
        )

    return {**state, "excel_context_snippet": "\n\n".join(chunks)}
