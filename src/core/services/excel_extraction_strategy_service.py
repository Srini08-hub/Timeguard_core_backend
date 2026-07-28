from __future__ import annotations

from typing import Literal

ExcelExtractionStrategy = Literal["entire_sheet", "semantic_split"]
_ALLOWED_STRATEGIES = {"entire_sheet", "semantic_split"}
SEMANTIC_WINDOW_ROWS = 8


class ExcelExtractionStrategyService:
    """In-process strategy selector used when enqueueing Excel extraction work."""

    def __init__(self) -> None:
        self._strategy: ExcelExtractionStrategy = "entire_sheet"

    def get_strategy(self) -> ExcelExtractionStrategy:
        return self._strategy

    def set_strategy(self, strategy: str) -> ExcelExtractionStrategy:
        if strategy not in _ALLOWED_STRATEGIES:
            allowed = ", ".join(sorted(_ALLOWED_STRATEGIES))
            raise ValueError(f"Invalid Excel extraction strategy. Expected one of: {allowed}")
        self._strategy = strategy  # type: ignore[assignment]
        return self._strategy

    def status(self) -> dict[str, object]:
        return {
            "excel_extraction_strategy": self._strategy,
            "semantic_window_rows": SEMANTIC_WINDOW_ROWS,
        }


excel_extraction_strategy_service = ExcelExtractionStrategyService()
