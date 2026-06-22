import logging

from langchain_core.runnables import RunnableConfig

from src.control.agents.excel_extract_node.groq_caller import call_groq
from src.control.agents.excel_extract_node.llm_client import extract_with_retries
from src.control.agents.excel_extract_node.prompts import (
    build_extraction_messages,
    build_system_prompt,
)
from src.control.agents.graph_config import get_db_session
from src.control.agents.state import BlockResult, TimeguardState
from src.core.exceptions.llm_exception import ExtractionError
from src.data.repositories.timesheet_repository import TimesheetRepository
from src.llm_trace_debug import store_llm_result_for_testing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _append_block_result_to_timesheet(
    state: TimeguardState,
    config: RunnableConfig,
    parsed_payload: dict,
) -> None:
    attachments = list(state.get("attachments", []))
    index = state.get("current_attachment_index", 0)
    if index >= len(attachments):
        logger.warning(
            "Skipping Excel payload persistence because attachment index %d "
            "is out of range",
            index,
        )
        return

    attachment = attachments[index]
    timesheet_id = attachment.get("timesheet_id")
    if timesheet_id is None:
        logger.warning(
            "Skipping Excel payload persistence because timesheet_id "
            "is missing for attachment %s",
            attachment.get("file_name", "<unknown>"),
        )
        return

    db_session = get_db_session(config)
    timesheet_repository = TimesheetRepository(db_session)
    timesheet = await timesheet_repository.append_extracted_payload(
        timesheet_id=timesheet_id,
        parsed_payload=parsed_payload,
    )
    if timesheet is None:
        return

    await db_session.commit()
    logger.info("Stored Excel parsed payload for timesheet %s", timesheet_id)


async def node_extract_block_with_llm(
    state: TimeguardState,
    config: RunnableConfig,
) -> dict:
    """
    Part B entry point for ONE sheet: Layer 1 (prompt) -> Layer 2/3
    (parse JSON, retry malformed JSON) via llm_client.extract_with_retries.

    Any ExtractionError here is caught and turned into a BlockResult
    with success=False, rather than propagating and aborting the other
    blocks' Send() branches.
    """
    block = state["blocks"][state["current_excel_block_index"]]
    system_prompt = build_system_prompt()
    messages = build_extraction_messages(block.text_payload)

    try:
        parsed = extract_with_retries(
            call_llm=call_groq,
            system_prompt=system_prompt,
            messages=messages,
        )
        trace_path = store_llm_result_for_testing(
            source="excel",
            payload=parsed,
            extra={
                "sheet_name": block.sheet_name,
                "block_index": block.block_index,
            },
        )
        logger.info("Stored Excel extraction result for testing at %s", trace_path)
        await _append_block_result_to_timesheet(state, config, parsed)

        result: BlockResult = {
            "sheet_name": block.sheet_name,
            "block_index": block.block_index,
            "success": True,
            "extraction": parsed,
            "error": None,
            "raw_response_on_failure": None,
        }
    except ExtractionError as e:
        logger.error(
            "Sheet block %d of sheet '%s' failed extraction permanently: %s",
            block.block_index,
            block.sheet_name,
            e,
        )
        result = {
            "sheet_name": block.sheet_name,
            "block_index": block.block_index,
            "success": False,
            "extraction": None,
            "error": str(e),
            "raw_response_on_failure": e.raw_response,
        }

    return {"results": [result]}
