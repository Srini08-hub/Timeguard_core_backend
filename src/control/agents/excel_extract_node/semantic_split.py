from __future__ import annotations

import logging
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.control.agents.excel_extract_node.probe_extract import (
    SerialisedBlock,
    SheetProbe,
    _col_letter,
    is_blank_token,
    normalise_cell,
)
from src.control.agents.llm_key_rotation import invoke_groq_structured_with_key_rotation
from src.core.services.excel_extraction_strategy_service import SEMANTIC_WINDOW_ROWS

logger = logging.getLogger(__name__)

MODEL_NAME = "llama-3.3-70b-versatile"
SPLIT_SYSTEM_PROMPT = """You are choosing the safest split point for Excel timesheet rows.

Return the best row number to split after.
Prefer:
1. after a complete employee block
2. before a new employee starts
3. otherwise safest row boundary

Do not extract timesheet data.
Return only structured split decision."""


class SemanticSplitDecision(BaseModel):
    best_split_after_row: int = Field(
        description="Original Excel row number after which the current chunk should end."
    )
    split_type: Literal[
        "employee_boundary",
        "department_boundary",
        "table_boundary",
        "row_boundary",
        "no_safe_split",
    ]
    confidence: float = Field(ge=0, le=1)
    reason: str


class SemanticSplitError(RuntimeError):
    pass


class _SerialisedRow(BaseModel):
    row_number: int
    text: str


def _serialise_rows(probe: SheetProbe) -> list[_SerialisedRow]:
    rows: list[_SerialisedRow] = []
    for row_number in range(probe.min_row, probe.max_row + 1):
        cells = []
        for col_number in range(probe.min_col, probe.max_col + 1):
            token = normalise_cell(probe.value(row_number, col_number))
            if is_blank_token(token):
                continue
            cells.append(f"{_col_letter(col_number)}{row_number}: {token}")
        if cells:
            rows.append(
                _SerialisedRow(
                    row_number=row_number,
                    text=f"R{row_number}: " + " | ".join(cells),
                )
            )
    return rows


def _build_splitter_user_prompt(
    *,
    sheet_name: str,
    window_rows: list[_SerialisedRow],
) -> str:
    first_row = window_rows[0].row_number
    last_row = window_rows[-1].row_number
    rows_text = "\n".join(row.text for row in window_rows)
    return (
        f"Sheet name: {sheet_name}\n"
        f"Window row range: {first_row}-{last_row}\n"
        "Rows use original Excel row numbers. Choose best_split_after_row from one "
        "of the row numbers shown below.\n\n"
        f"{rows_text}"
    )


def _choose_split_row(sheet_name: str, window_rows: list[_SerialisedRow]) -> int:
    response = invoke_groq_structured_with_key_rotation(
        model_name=MODEL_NAME,
        output_schema=SemanticSplitDecision,
        messages=[
            SystemMessage(content=SPLIT_SYSTEM_PROMPT),
            HumanMessage(
                content=_build_splitter_user_prompt(
                    sheet_name=sheet_name,
                    window_rows=window_rows,
                )
            ),
        ],
        preferred_key_name="GROQ_API_KEY_3",
        operation_name="Excel semantic split decision",
    )

    if not isinstance(response, SemanticSplitDecision):
        raise SemanticSplitError(f"Invalid semantic split response type: {type(response)!r}")
    if response.split_type == "no_safe_split":
        raise SemanticSplitError(
            f"No safe split returned for sheet {sheet_name}: {response.reason}"
        )
    if response.confidence < 0.5:
        raise SemanticSplitError(
            f"Low-confidence split for sheet {sheet_name}: "
            f"{response.confidence}. {response.reason}"
        )

    allowed_rows = {row.row_number for row in window_rows}
    if response.best_split_after_row not in allowed_rows:
        raise SemanticSplitError(
            f"Split row {response.best_split_after_row} is not inside window "
            f"{window_rows[0].row_number}-{window_rows[-1].row_number}."
        )

    logger.info(
        "Semantic split for sheet %s after row %s (%s, confidence=%s): %s",
        sheet_name,
        response.best_split_after_row,
        response.split_type,
        response.confidence,
        response.reason,
    )
    return response.best_split_after_row


def _make_block(
    *,
    probe: SheetProbe,
    block_index: int,
    rows: list[_SerialisedRow],
    chunk_number: int,
    chunk_count: int | None = None,
) -> SerialisedBlock:
    first_row = rows[0].row_number
    last_row = rows[-1].row_number
    count_suffix = f"/{chunk_count}" if chunk_count is not None else ""
    lines = [
        (
            f"# Sheet: {probe.sheet_name} | Block: {block_index} | "
            f"Scope: semantic_split | Chunk: {chunk_number}{count_suffix} | "
            f"Rows: {first_row}-{last_row} | "
            f"Columns: {_col_letter(probe.min_col)}-{_col_letter(probe.max_col)} | "
            f"Merges resolved: {probe.merge_count}"
        ),
        "",
        "Semantic split metadata:",
        "- Strategy: semantic_split",
        f"- Window rows: {SEMANTIC_WINDOW_ROWS}",
        "- Extract only the rows in this chunk. If the chunk continues an employee, "
        "use row numbers and visible context to preserve continuity.",
        "",
        "Cells:",
        *[row.text for row in rows],
    ]
    return SerialisedBlock(
        sheet_name=probe.sheet_name,
        block_index=block_index,
        orientation="sheet",
        header_descriptor="semantic_split",
        n_records=len(rows),
        n_merges_resolved=probe.merge_count,
        text_payload="\n".join(lines).rstrip() + "\n",
    )


def serialise_sheet_semantic_split(
    probe: SheetProbe,
    *,
    first_block_index: int,
    window_rows: int = SEMANTIC_WINDOW_ROWS,
) -> list[SerialisedBlock]:
    if window_rows < 2:
        raise SemanticSplitError("Semantic split window_rows must be at least 2.")

    pending_rows = _serialise_rows(probe)
    if not pending_rows:
        return []

    chunks: list[list[_SerialisedRow]] = []
    while len(pending_rows) > window_rows:
        window = pending_rows[:window_rows]
        split_after_row = _choose_split_row(probe.sheet_name, window)
        split_index = next(
            index
            for index, row in enumerate(pending_rows)
            if row.row_number == split_after_row
        )
        chunk = pending_rows[: split_index + 1]
        if not chunk:
            raise SemanticSplitError(
                f"Semantic split produced an empty chunk for sheet {probe.sheet_name}."
            )
        chunks.append(chunk)
        pending_rows = pending_rows[split_index + 1 :]

    if pending_rows:
        chunks.append(pending_rows)

    chunk_count = len(chunks)
    return [
        _make_block(
            probe=probe,
            block_index=first_block_index + index,
            rows=chunk,
            chunk_number=index + 1,
            chunk_count=chunk_count,
        )
        for index, chunk in enumerate(chunks)
    ]
