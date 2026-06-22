import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.control.agents.digital_extract_node.llm_client import extract_with_retries
from src.control.agents.digital_extract_node.prompts import (
    build_extraction_messages,
    build_system_prompt,
)
from src.control.agents.excel_extract_node.groq_caller import call_groq
from src.control.agents.graph_config import get_db_session
from src.control.agents.state import TimeguardState
from src.core.exceptions.llm_exception import ExtractionError
from src.data.repositories.timesheet_repository import TimesheetRepository
from src.llm_trace_debug import store_llm_result_for_testing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _store_timesheet_payload(
    state: TimeguardState,
    config: RunnableConfig,
    payload: list[dict[str, Any]] | None,
) -> None:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    if index >= len(attachments):
        logger.warning(
            "Skipping timesheet payload save because attachment index is out of range"
        )
        return

    attachment = attachments[index]
    timesheet_id = attachment.get("timesheet_id")
    if timesheet_id is None:
        logger.warning(
            "Skipping timesheet payload save because timesheet_id "
            "is missing for attachment %s",
            attachment.get("file_name", "<unknown>"),
        )
        return

    db_session = get_db_session(config)
    timesheet_repository = TimesheetRepository(db_session)
    timesheet = await timesheet_repository.set_extracted_payload(
        timesheet_id=timesheet_id,
        extracted_payload={"blocks": payload},
    )
    if timesheet is None:
        return

    await db_session.commit()
    logger.info("Stored digital extraction payload for timesheet %s", timesheet_id)


async def node_extract_block_with_llm(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    blocks = state.get("d_blocks", [])
    if not isinstance(blocks, list):
        blocks = [blocks]

    system_prompt = build_system_prompt()
    results: list[dict[str, Any]] = []

    logger.info("Starting digital LLM extraction for %d block(s)", len(blocks))

    for block in blocks:
        messages = build_extraction_messages(block.text_payload)

        try:
            parsed = extract_with_retries(
                call_llm=call_groq,
                system_prompt=system_prompt,
                messages=messages,
            )
            logger.info("Digital block %d extracted successfully", block.block_index)
            results.append(
                {
                    "block_index": block.block_index,
                    "success": True,
                    "extraction": parsed,
                    "error": None,
                    "raw_response_on_failure": None,
                }
            )
            await _store_timesheet_payload(state, config, results)
        except ExtractionError as e:
            logger.error(
                "Digital block %d failed extraction permanently: %s",
                block.block_index,
                e,
            )
            results.append(
                {
                    "block_index": block.block_index,
                    "success": False,
                    "extraction": None,
                    "error": str(e),
                    "raw_response_on_failure": e.raw_response,
                }
            )

    trace_path = store_llm_result_for_testing(
        source="digital",
        payload=results,
        extra={"block_count": len(blocks)},
    )
    logger.info("Stored digital extraction result for testing at %s", trace_path)

    return state
