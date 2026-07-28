from fastapi import APIRouter, HTTPException, status

from src.core.services.excel_extraction_strategy_service import (
    excel_extraction_strategy_service,
)
from src.schemas.operation_settings_schema import (
    ExcelExtractionStrategyRequest,
    ExcelExtractionStrategyResponse,
)

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get(
    "/excel-extraction-strategy",
    response_model=ExcelExtractionStrategyResponse,
    status_code=status.HTTP_200_OK,
)
async def get_excel_extraction_strategy() -> ExcelExtractionStrategyResponse:
    return ExcelExtractionStrategyResponse(**excel_extraction_strategy_service.status())


@router.patch(
    "/excel-extraction-strategy",
    response_model=ExcelExtractionStrategyResponse,
    status_code=status.HTTP_200_OK,
)
async def update_excel_extraction_strategy(
    payload: ExcelExtractionStrategyRequest,
) -> ExcelExtractionStrategyResponse:
    try:
        excel_extraction_strategy_service.set_strategy(payload.excel_extraction_strategy)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ExcelExtractionStrategyResponse(**excel_extraction_strategy_service.status())
