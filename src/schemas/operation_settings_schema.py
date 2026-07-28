from typing import Literal

from pydantic import BaseModel, Field

ExcelExtractionStrategy = Literal["entire_sheet", "semantic_split"]


class ExcelExtractionStrategyRequest(BaseModel):
    excel_extraction_strategy: ExcelExtractionStrategy


class ExcelExtractionStrategyResponse(BaseModel):
    excel_extraction_strategy: ExcelExtractionStrategy
    semantic_window_rows: int = Field(default=8)
