"""Merge node for consolidating extracted timesheet data from multiple sources."""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from langchain_core.runnables import RunnableConfig

from src.control.agents.graph_config import get_db_session
from src.control.agents.state import TimeguardState
from src.control.agents.timesheet_schema import EmployeeRecord, MergeResponse
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


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def _non_empty_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_decimal(value: Any) -> Decimal | None:
    if _is_missing(value):
        return None
    try:
        return Decimal(str(value).strip())
    except Exception:
        return None


def _parse_time(value: Any) -> datetime | None:
    if _is_missing(value):
        return None

    text = str(value).strip()
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _duration_hours(check_in: Any, check_out: Any) -> Decimal | None:
    start = _parse_time(check_in)
    end = _parse_time(check_out)
    if start is None or end is None:
        return None
    if end < start:
        end += timedelta(days=1)
    seconds = Decimal(str((end - start).total_seconds()))
    return (seconds / Decimal("3600")).quantize(Decimal("0.01"))


def _calculate_hours_from_check_in_out(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Calculate hours from check_in and check_out if hours is not provided."""
    for record in records:
        timesheet_records = record.get("timesheet_records") or []
        if not isinstance(timesheet_records, list):
            continue

        for timesheet_record in timesheet_records:
            if not isinstance(timesheet_record, dict):
                continue

            hours = _to_decimal(timesheet_record.get("hours"))
            total_hours = _to_decimal(timesheet_record.get("total_hours"))
            check_in = timesheet_record.get("check_in")
            check_out = timesheet_record.get("check_out")

            if (
                hours is None
                and total_hours is None
                and not _is_missing(check_in)
                and not _is_missing(check_out)
            ):
                calculated_hours = _duration_hours(check_in, check_out)
                if calculated_hours is not None:
                    timesheet_record["hours"] = str(calculated_hours)

    return records


def _is_merge_response_payload(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("global_data"), dict)
        and isinstance(value.get("employee_records"), list)
    )


def _iter_raw_merge_payloads(payload: Any) -> Any:
    """Yield raw MergeResponse-shaped dicts from persisted extractor payloads."""
    if payload is None:
        return

    if isinstance(payload, list):
        for item in payload:
            yield from _iter_raw_merge_payloads(item)
        return

    if not isinstance(payload, dict):
        return

    if _is_merge_response_payload(payload):
        yield payload
        return

    extraction = payload.get("extraction")
    if extraction is not None:
        yield from _iter_raw_merge_payloads(extraction)


def _load_extracted_merge_responses(
    extracted_data: list[dict[str, Any]],
) -> list[MergeResponse]:
    responses: list[MergeResponse] = []
    for source_index, source in enumerate(extracted_data, start=1):
        payload = source.get("extracted_payload")
        for raw_payload in _iter_raw_merge_payloads(payload):
            try:
                responses.append(MergeResponse.model_validate(raw_payload))
            except Exception as exc:
                logger.warning(
                    "Skipping invalid extracted payload from source %d (%s): %s",
                    source_index,
                    source.get("attachment_name", "unknown"),
                    exc,
                )
    return responses


def _employee_key(employee_name: str) -> str:
    return employee_name.strip().casefold()


def _merge_source_lists(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen = {(source.get("file_name"), source.get("content_type")) for source in existing}
    for source in incoming:
        key = (source.get("file_name"), source.get("content_type"))
        if key not in seen:
            existing.append(source)
            seen.add(key)
    return existing


def _merge_employee_record(
    merged_employee: dict[str, Any],
    incoming_employee: EmployeeRecord,
) -> None:
    incoming = incoming_employee.model_dump()

    if not _non_empty_text(merged_employee.get("department")):
        department = _non_empty_text(incoming.get("department"))
        if department:
            merged_employee["department"] = department

    merged_employee["source"] = _merge_source_lists(
        merged_employee.get("source") or [],
        incoming.get("source") or [],
    )
    merged_employee.setdefault("timesheet_records", []).extend(
        incoming.get("timesheet_records") or []
    )


def _combine_merge_responses(responses: list[MergeResponse]) -> dict[str, Any]:
    combined_global_data: dict[str, Any] = {
        "client_name": None,
        "week_ending": None,
    }
    employees_by_name: dict[str, dict[str, Any]] = {}

    for response in responses:
        global_data = response.global_data.model_dump()
        if not _non_empty_text(combined_global_data.get("client_name")):
            combined_global_data["client_name"] = _non_empty_text(
                global_data.get("client_name")
            )
        if not _non_empty_text(combined_global_data.get("week_ending")):
            combined_global_data["week_ending"] = _non_empty_text(
                global_data.get("week_ending")
            )

        for employee in response.employee_records:
            key = _employee_key(employee.employee_name)
            if key not in employees_by_name:
                employees_by_name[key] = employee.model_dump()
                continue
            _merge_employee_record(employees_by_name[key], employee)

    return {
        "global_data": combined_global_data,
        "employee_records": list(employees_by_name.values()),
    }


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

    if not extracted_data:
        logger.warning("No extracted data found for email %s, skipping merge", email_id)
        return state

    try:
        merge_responses = _load_extracted_merge_responses(extracted_data)
        if not merge_responses:
            raise ValueError("No structured extraction payloads available for merge")

        payload = _combine_merge_responses(merge_responses)

        # Step 3: Store result as JSON file for testing
        trace_path = store_llm_result_for_testing(
            source="merge",
            payload=payload,
            extra={
                "email_id": str(email_id),
                "source_count": len(extracted_data),
                "structured_payload_count": len(merge_responses),
            },
        )
        logger.info("Stored merge result for testing at %s", trace_path)

        # Step 4: Extract client_name and week_ending from payload
        global_data = payload.get("global_data", {})
        client_name = global_data.get("client_name")
        week_ending_str = global_data.get("week_ending")
        if week_ending_str is None:
            raise ValueError("week_ending is not available in payload")
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
            raise ValueError("week_ending is not available in payload")
        payload["employee_records"] = _calculate_hours_from_check_in_out(
            payload.get("employee_records", [])
        )
        # Step 5: Create timesheet record with payload
        timesheet_repository = TimesheetRepository(db_session)
        await timesheet_repository.create_with_merge_data(
            email_id=email_id,
            client_name=client_name,
            week_ending=week_ending,
            payload=payload,
        )
        await db_session.commit()

        # Step 6: Update email status to MERGED
        email_repository = EmailRepository(db_session)
        email = await email_repository.get_by_id(email_id)
        if email:
            await email_repository.set_status(email, EmailStatus.MERGED)
            logger.info("Set email %s status to MERGED", email_id)

        await db_session.commit()
        # Update state with payload
        result = cast(
            TimeguardState,
            {
                **state,
                "payload": payload,
                # "merge_source_count": len(extracted_data),
            },
        )

        logger.info(
            "Successfully merged %d structured payload(s) from %d sources for email %s",
            len(merge_responses),
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
