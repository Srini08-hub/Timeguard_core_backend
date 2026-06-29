"""Merge node for consolidating extracted timesheet data from multiple sources."""

import logging
from datetime import datetime
from typing import Any, cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field, field_validator

from src.config.settings import settings
from src.control.agents.graph_config import get_db_session
from src.control.agents.merge_node.prompts import (
    build_merge_messages,
    build_system_prompt,
)
from src.control.agents.state import TimeguardState
from src.data.models.email import EmailStatus
from src.data.repositories.content_extract_repository import ContentExtractRepository
from src.data.repositories.email_repository import EmailRepository
from src.data.repositories.timesheet_repository import TimesheetRepository
from src.llm_trace_debug import store_llm_result_for_testing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATE_FORMATS = [
    "%Y-%m-%d",
    "%d-%b-%Y",
    "%d/%m/%y",
    "%d/%m/%Y",
]


class TimesheetRecord(BaseModel):
    """timesheet record in timesheet."""

    date: str | None = Field(description="Date in YYYY-MM-DD format")
    check_in: str | None = Field(default=None, description="Check-in time in HH:MM format")
    check_out: str | None = Field(default=None, description="Check-out time in HH:MM format")
    break_hour: str | None = Field(default=None, description="Break time in HH:MM format")
    hours: str | None = Field(default=None, description="Daily Hours worked")
    total_hours: str | None = Field(default=None, description="Total Hours worked")
    overtime_hours: str | None = Field(default=None, description="Overtime hours")
    confidence: float | None = Field(default=None, description="Confidence score")

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> float | None:
        if v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None


class SourceInfo(BaseModel):
    """Source information for employee record."""

    file_name: str = Field(description="File name")
    content_type: str = Field(description="Content type (excel, pdf, email)")


class EmployeeRecord(BaseModel):
    """Employee record in timesheet."""

    employee_name: str = Field(description="Employee name")
    department: str | None = Field(default=None, description="Department")
    source: list[SourceInfo] = Field(description="Source information")
    timesheet_records: list[TimesheetRecord] = Field(description="Timesheet records")


class GlobalData(BaseModel):
    """Global timesheet data."""

    client_name: str | None = Field(default=None, description="Client name")
    week_ending: str | None = Field(default=None, description="Week ending date")


class MergeResponse(BaseModel):
    """Structured response from the merge LLM."""

    global_data: GlobalData = Field(description="Global timesheet data")
    employee_records: list[EmployeeRecord] = Field(description="Employee records")


# def _non_empty_text(value: Any) -> str | None:
#     if value is None:
#         return None

#     text = str(value).strip()
#     return text or None


# def _walk_values(value: Any):
#     if isinstance(value, dict):
#         yield value
#         for nested in value.values():
#             yield from _walk_values(nested)
#     elif isinstance(value, list):
#         for item in value:
#             yield from _walk_values(item)


# def _department_from_payload(payload: Any) -> str | None:
#     extraction_objects = [
#         item for item in _walk_values(payload)
#         if isinstance(item.get("rows"), list) or isinstance(item.get("global_fields"), dict)
#     ]

#     for extraction in extraction_objects:
#         for row in extraction.get("rows") or []:
#             if not isinstance(row, dict):
#                 continue
#             department = _non_empty_text(row.get("department") or row.get("dept"))
#             if department:
#                 return department

#     for extraction in extraction_objects:
#         global_fields = extraction.get("global_fields") or {}
#         if isinstance(global_fields, dict):
#             department = _non_empty_text(
#                 global_fields.get("department") or global_fields.get("dept")
#             )
#             if department:
#                 return department

#     return None


# def _apply_source_departments(
#     merged_result: dict[str, Any],
#     extracted_data: list[dict[str, Any]],
# ) -> dict[str, Any]:
#     department_by_source: dict[str, str] = {}
#     for source in extracted_data:
#         attachment_name = _non_empty_text(source.get("attachment_name"))
#         department = _department_from_payload(source.get("extracted_payload"))
#         if attachment_name and department:
#             department_by_source.setdefault(attachment_name, department)

#     if not department_by_source:
#         return merged_result

#     employee_records = merged_result.get("employee_records") or []
#     if isinstance(employee_records, list):
#         for record in employee_records:
#             if not isinstance(record, dict) or _non_empty_text(record.get("department")):
#                 continue

#             source = record.get("source") or {}
#             file_name = source.get("file_name") if isinstance(source, dict) else None
#             department = department_by_source.get(str(file_name).strip())
# if file_name
#  else None
#             if department:
#                 record["department"] = department

#     unique_departments = sorted(set(department_by_source.values()))
#     global_data = merged_result.setdefault("global_data", {})
#     if (
#         isinstance(global_data, dict)
#         and len(unique_departments) == 1
#         and not _non_empty_text(global_data.get("department"))
#     ):
#         global_data["department"] = unique_departments[0]

#     return merged_result


async def merge_node(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    """Merge extracted data from all content_extract records for an email.

    Args:
        state: Current state containing email_id
        config: RunnableConfig for database session

    Returns:
        Updated state with merged result
    """
    email_id = state.get("email_id")
    if email_id is None:
        logger.warning("Skipping merge because email_id is missing")
        return state

    logger.info("Starting merge node for email %s", email_id)

    # Step 1: Load data from content_extract table using repository
    db_session = get_db_session(config)
    content_extract_repository = ContentExtractRepository(db_session)
    extracted_data = await content_extract_repository.get_extracted_data_for_merge(
        email_id=email_id,
    )

    # Step 1.5: If email body is not a timesheet, append email body text to extracted data
    email_body_classification = state.get("email_body_classification")
    if email_body_classification != "TIMESHEET":
        email_body = state.get("body")
        if email_body:
            logger.info(
                "Email body is not a timesheet, appending email body text to extracted data"
            )
            extracted_data.append(
                {
                    "extracted_payload": {"email_body_text": email_body},
                    "source_type": "email_body_text",
                    "attachment_name": "email_body",
                }
            )

    if not extracted_data:
        logger.warning("No extracted data found for email %s, skipping merge", email_id)
        return state

    # Step 2: Prefer deterministic row merge for extractor-normalized tables.
    try:
        system_prompt = build_system_prompt()
        messages = build_merge_messages(extracted_data)
        llm = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            # model_name="qwen/qwen3-32b",
            temperature=0,
            api_key=settings.GROQ_API_KEY,
        )
        structured_llm = llm.with_structured_output(MergeResponse)
        response = structured_llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=messages[0]["content"]),
            ]
        )

        if not isinstance(response, MergeResponse):
            raise ValueError("Invalid merge response type")

        merged_result = response.model_dump(exclude_none=True)

        # Step 3: Store result as JSON file for testing
        trace_path = store_llm_result_for_testing(
            source="merge",
            payload=merged_result,
            extra={
                "email_id": str(email_id),
                "source_count": len(extracted_data),
            },
        )
        logger.info("Stored merge result for testing at %s", trace_path)

        # Step 4: Extract client_name and week_ending from merged_result
        global_data = merged_result.get("global_data", {})
        client_name = global_data.get("client_name")
        week_ending_str = global_data.get("week_ending")
        if week_ending_str is None:
            raise ValueError("week_ending is not available in merged_result")
        week_ending = None

        if week_ending_str:
            for fmt in DATE_FORMATS:
                try:
                    week_ending = datetime.strptime(week_ending_str, fmt).date()
                    break
                except ValueError:
                    continue

        if week_ending is None:
            logger.warning(
                "Failed to parse week_ending '%s' for email %s",
                week_ending_str,
                email_id,
            )
            raise ValueError("week_ending is not available in merged_result")

        # Step 5: Create timesheet record with merge data
        timesheet_repository = TimesheetRepository(db_session)
        await timesheet_repository.create_with_merge_data(
            email_id=email_id,
            client_name=client_name,
            week_ending=week_ending,
            merged_payload=merged_result,
        )
        await db_session.commit()

        # Step 6: Update email status to MERGED
        email_repository = EmailRepository(db_session)
        email = await email_repository.get_by_id(email_id)
        if email:
            await email_repository.set_status(email, EmailStatus.MERGED)
            logger.info("Set email %s status to MERGED", email_id)

        await db_session.commit()
        # Update state with merged result
        result = cast(
            TimeguardState,
            {
                **state,
                "merged_result": merged_result,
                # "merge_source_count": len(extracted_data),
            },
        )

        logger.info(
            "Successfully merged %d sources for email %s",
            len(extracted_data),
            email_id,
        )
        return result

    except Exception as e:
        logger.error("Merge failed for email %s: %s", email_id, e)

        # Update email status to FAILED with failure stage and reason
        email_repository = EmailRepository(db_session)
        email = await email_repository.get_by_id(email_id)
        if email:
            await email_repository.set_status(
                email,
                EmailStatus.FAILED,
                failure_stage="merge",
                failure_reason=str(e),
            )
            logger.info("Set email %s status to FAILED with stage 'merge'", email_id)

        await db_session.commit()

        # Store error for testing
        store_llm_result_for_testing(
            source="merge",
            payload={
                "success": False,
                "error": str(e),
                "email_id": str(email_id),
                "source_count": len(extracted_data),
            },
            extra={"email_id": str(email_id)},
        )

        return state
