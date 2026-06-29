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
from src.data.models.email import EmailStatus
from src.data.repositories.attachment_repository import AttachmentRepository
from src.data.repositories.content_extract_repository import ContentExtractRepository
from src.data.repositories.email_repository import EmailRepository
from src.llm_trace_debug import store_llm_result_for_testing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _append_block_result_to_content_extract(
    state: TimeguardState,
    config: RunnableConfig,
    parsed_payload: dict,
) -> None:
    attachments = list(state.get("attachments", []))
    index = state.get("current_attachment_index", 0)
    if index >= len(attachments):
        logger.warning(
            "Skipping Excel payload persistence because attachment index %d is out of range",
            index,
        )
        return

    attachment = attachments[index]
    content_extract_id = attachment.get("content_extract_id")
    if content_extract_id is None:
        logger.warning(
            "Skipping Excel payload persistence because content_extract_id "
            "is missing for attachment %s",
            attachment.get("file_name", "<unknown>"),
        )
        return

    db_session = get_db_session(config)
    content_extract_repository = ContentExtractRepository(db_session)

    logger.info(
        "Appending payload for sheet '%s' to content_extract %s. Payload: %s",
        parsed_payload.get("sheet_name", "unknown"),
        content_extract_id,
        parsed_payload,
    )

    content_extract = await content_extract_repository.append_extracted_payload(
        content_extract_id=content_extract_id,
        parsed_payload=parsed_payload,
    )
    if content_extract is None:
        return

    await db_session.commit()
    logger.info(
        "Successfully stored Excel parsed payload for content_extract %s."
        " Current payload count: %s",
        content_extract_id,
        len(content_extract.extracted_payload)
        if isinstance(content_extract.extracted_payload, list)
        else 1,
    )


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

    extraction_failed = False
    failure_reason = None

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
        await _append_block_result_to_content_extract(state, config, parsed)

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
        extraction_failed = True
        failure_reason = str(e)
        result = {
            "sheet_name": block.sheet_name,
            "block_index": block.block_index,
            "success": False,
            "extraction": None,
            "error": str(e),
            "raw_response_on_failure": e.raw_response,
        }
    except Exception as e:
        logger.exception(
            "Unexpected error during Excel block extraction for sheet '%s' block %d: %s",
            block.sheet_name,
            block.block_index,
            e,
        )
        extraction_failed = True
        failure_reason = str(e)
        result = {
            "sheet_name": block.sheet_name,
            "block_index": block.block_index,
            "success": False,
            "extraction": None,
            "error": str(e),
            "raw_response_on_failure": None,
        }

    # Update email and attachment status if extraction failed
    if extraction_failed and failure_reason:
        db_session = get_db_session(config)
        email_repository = EmailRepository(db_session)
        attachment_repository = AttachmentRepository(db_session)

        # Update email status
        email_id = state.get("email_id")
        if email_id:
            email = await email_repository.get_by_id(email_id)
            if email:
                await email_repository.set_status(
                    email,
                    EmailStatus.FAILED,
                    failure_stage="excel_extraction",
                    failure_reason=failure_reason,
                )
                logger.info(
                    "Set email %s status to FAILED due to Excel extraction error", email_id
                )

        # Update attachment status
        attachments = state.get("attachments", [])
        index = state.get("current_attachment_index", 0)
        if index < len(attachments):
            attachment = attachments[index]
            attachment_db_id = attachment.get("attachment_db_id")
            if attachment_db_id:
                attachment_obj = await attachment_repository.get_by_id(attachment_db_id)
                if attachment_obj:
                    await attachment_repository.set_failed(
                        attachment_obj,
                        failure_stage="excel_extraction",
                        failure_reason=failure_reason,
                    )
                    logger.info(
                        "Set attachment %s status to FAILED due to Excel extraction error",
                        attachment_db_id,
                    )

        await db_session.commit()
        raise Exception(f"Excel extraction failed: {failure_reason}")

    return {"results": [result]}
