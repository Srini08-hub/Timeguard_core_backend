from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

if TYPE_CHECKING:
    from src.control.agents.state import AttachmentState, TimeguardState
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("timesheet_extractor")

EMPTY_TOKEN = "—"
TRACE_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "llm_traces" / "excel_extraction"


@dataclass
class SerialisedBlock:
    sheet_name: str
    block_index: int
    orientation: str
    header_descriptor: str
    n_records: int
    n_merges_resolved: int
    text_payload: str


@dataclass
class SheetProbe:
    """Everything Phase 1+2 produce for a single worksheet."""

    sheet_name: str
    min_row: int
    max_row: int
    min_col: int
    max_col: int
    merge_map: dict[tuple[int, int], Any] = field(default_factory=dict)
    merge_count: int = 0
    # ws_formulas: Worksheet = field(repr=False, default=None)
    ws_values: Worksheet = field(repr=False, default=None)

    # def raw(self, row: int, col: int) -> Any:
    #     """Literal cell content, resolved through merge_map first."""
    #     if (row, col) in self.merge_map:
    #         return self.merge_map[(row, col)]
    #     return self.ws_formulas.cell(row=row, column=col).value

    # def cached(self, row: int, col: int) -> Any:
    #     """Cached computed value for the same cell (data_only=True pass)."""
    #     if (row, col) in self.merge_map:
    #         return self.merge_map[(row, col)]
    #     return self.ws_values.cell(row=row, column=col).value
    def value(self, row: int, col: int) -> Any:
        """Cell value with merged-cell resolution."""
        if (row, col) in self.merge_map:
            return self.merge_map[(row, col)]
        return self.ws_values.cell(row=row, column=col).value


def probe_workbook(path: str) -> dict[str, SheetProbe]:
    """
    Phase 1+2 entry point.

    Returns a dict of {sheet_name: SheetProbe} so a multi-sheet workbook
    can be processed sheet-by-sheet by the caller/graph.
    """
    # wb_formulas = openpyxl.load_workbook(path, data_only=False)
    wb_values = openpyxl.load_workbook(path, data_only=True)

    sheet_names = wb_values.sheetnames
    probes: dict[str, SheetProbe] = {}

    for name in sheet_names:
        # ws_f = wb_formulas[name]
        ws_v = wb_values[name]

        # Snapshot merge ranges FIRST, before any other iteration —
        # openpyxl can lose/alter merge metadata once you start writing
        # or in some versions even reading triggers lazy unmerge state.
        merge_ranges = list(ws_v.merged_cells.ranges)

        min_row, max_row = ws_v.min_row, ws_v.max_row
        min_col, max_col = ws_v.min_column, ws_v.max_column

        merge_map: dict[tuple[int, int], Any] = {}
        for rng in merge_ranges:
            anchor_value = ws_v.cell(row=rng.min_row, column=rng.min_col).value
            for r in range(rng.min_row, rng.max_row + 1):
                for c in range(rng.min_col, rng.max_col + 1):
                    merge_map[(r, c)] = anchor_value

        probes[name] = SheetProbe(
            sheet_name=name,
            min_row=min_row,
            max_row=max_row,
            min_col=min_col,
            max_col=max_col,
            merge_map=merge_map,
            merge_count=len(merge_ranges),
            ws_values=ws_v,
        )

    return probes


def _col_letter(col_idx: int) -> str:
    letters = ""
    n = col_idx
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def serialise_sheet(probe: SheetProbe, block_index: int = 0) -> SerialisedBlock:
    """
    Serialise one whole worksheet as one LLM payload.

    This keeps sheet-level labels, metadata, and tables together so the LLM
    can semantically map values to nearby labels instead of receiving
    pre-split table records.
    """
    lines = [
        (
            f"# Sheet: {probe.sheet_name} | Block: {block_index} | Scope: full_sheet | "
            f"Rows: {probe.min_row}-{probe.max_row} |"
            f" Columns: {_col_letter(probe.min_col)}-{_col_letter(probe.max_col)} | "
            f"Merges resolved: {probe.merge_count}"
        ),
        "",
        "Cells:",
    ]

    non_empty_rows = 0
    non_empty_cells = 0
    for r in range(probe.min_row, probe.max_row + 1):
        cells = []
        for c in range(probe.min_col, probe.max_col + 1):
            token = normalise_cell(probe.value(r, c))
            if is_blank_token(token):
                continue
            cells.append(f"{_col_letter(c)}{r}: {token}")
        if cells:
            non_empty_rows += 1
            non_empty_cells += len(cells)
            lines.append(f"R{r}: " + " | ".join(cells))

    return SerialisedBlock(
        sheet_name=probe.sheet_name,
        block_index=block_index,
        orientation="sheet",
        header_descriptor="full_sheet",
        n_records=non_empty_rows,
        n_merges_resolved=probe.merge_count,
        text_payload="\n".join(lines).rstrip() + "\n",
    )


def _collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def normalise_cell(value: Any) -> str:
    """Single entry point: routes to formula or scalar normalisation."""
    """
    Normalise a single literal (non-formula) cell value per Phase 4 rules:

    - None / "" -> EMPTY_TOKEN
    - datetime  -> ISO 8601
    - date      -> ISO 8601 (date only)
    - time      -> HH:MM
    - float < 1.0 -> treated as an Excel time fraction -> HH:MM
    - float ending in .0 -> cast to int -> str
    - other float -> round to 2 decimals
    - str starting with "=" -> caller should have routed this to the
      formula path already; defensively returns "[formula]" if it slips
      through.
    - other str -> stripped, internal whitespace collapsed
    """
    if value is None:
        return EMPTY_TOKEN
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return EMPTY_TOKEN
        if stripped.startswith("="):
            return "[formula]"
        return _collapse_ws(stripped)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, timedelta):
        total_minutes = int(value.total_seconds() // 60)
        h, m = divmod(total_minutes, 60)
        return f"{h:02d}:{m:02d}"
    if isinstance(value, bool):
        # bool is a subclass of int in Python; check before int/float.
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # Excel stores times-of-day as fractions of a 24h day when the
        # cell is *not* a typed `time` object (common when value_only
        # reads return raw floats instead of datetime.time).
        if 0.0 <= value < 1.0:
            total_minutes = round(value * 24 * 60)
            h, m = divmod(total_minutes, 60)
            return f"{h:02d}:{m:02d}"
        if value == int(value):
            return str(int(value))
        return f"{round(value, 2):.2f}"
    # Fallback for any exotic openpyxl type.
    return _collapse_ws(str(value))


def is_blank_token(token: str) -> bool:
    return token == EMPTY_TOKEN


def _current_attachment(state: TimeguardState) -> AttachmentState:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    if index >= len(attachments):
        raise ValueError("No attachment available for PDF processing")

    return attachments[index]


# def _resolve_attachment_path(attachment: AttachmentState) -> Path | None:
#     attachment_url = attachment.get("attachment_url")
#     if attachment_url:
#         parsed_url = urlparse(attachment_url)
#         candidate = settings.ATTACHMENT_STORAGE_DIR / Path(parsed_url.path).name
#         if candidate.exists():
#             return candidate

#     file_name = attachment.get("file_name")
#     if file_name:
#         matches = list(settings.ATTACHMENT_STORAGE_DIR.glob(f"*_{file_name}"))
#         if matches:
#             return matches[0]
#     return None


def _dump_blocks_for_trace(file_path: Path | str, blocks: list[SerialisedBlock]) -> Path:
    TRACE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    workbook_path = Path(file_path)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    trace_path = TRACE_OUTPUT_DIR / f"{workbook_path.stem}_{timestamp}.json"

    payload = {
        "source_workbook": str(workbook_path),
        "block_count": len(blocks),
        "blocks": [asdict(block) for block in blocks],
    }
    trace_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return trace_path


def excel_extraction_node(state: TimeguardState) -> dict:
    """Part A entry point: Phases 1-5 across the whole workbook."""
    attachement = _current_attachment(state)
    # file_path = _resolve_attachment_path(attachement)
    file_path = attachement.get("file_path")
    if file_path is None:
        raise ValueError("Could not resolve attachment path for Excel extraction")
    blocks = extract_workbook(str(file_path))
    trace_path = _dump_blocks_for_trace(file_path, blocks)
    logger.info("Probed workbook '%s': found %d sheet block(s).", file_path, len(blocks))
    logger.info("Saved Excel extraction trace to %s", trace_path)
    return {"current_excel_block_index": 0, "blocks": blocks}


def extract_workbook(path: str) -> list[SerialisedBlock]:
    """
    Process every selected worksheet as one block per sheet.

    If sheet_name is None, processes every sheet in the workbook. The returned
    list has one SerialisedBlock per non-empty sheet.
    """
    # probes = probe_workbook(path, sheet_name=sheet_name)
    probes = probe_workbook(path)
    logger.info("Probed workbook '%s': found %d sheet(s).", path, len(probes))
    logger.info("Probed sheets: %s", ", ".join(probes.keys()))

    results: list[SerialisedBlock] = []
    for index, probe in enumerate(probes.values()):
        serialised = serialise_sheet(probe, block_index=index)
        logger.info("Serialised sheet %d: %s", index, serialised)
        if serialised.n_records > 0:
            results.append(serialised)

    return results
