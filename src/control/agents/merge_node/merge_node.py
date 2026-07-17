"""Merge node for consolidating extracted timesheet data from multiple sources."""

import logging
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from langchain_core.runnables import RunnableConfig

from src.control.agents.graph_config import get_db_session
from src.control.agents.state import TimeguardState
from src.control.agents.timesheet_schema import MergeResponse
from src.data.models.email import EmailStatus
from src.data.repositories.content_extract_repository import ContentExtractRepository
from src.data.repositories.email_repository import EmailRepository
from src.data.repositories.timesheet_repository import TimesheetRepository

# LLM merge imports preserved for the commented implementation below:
# import json
# from langchain_core.messages import HumanMessage, SystemMessage
# from langchain_groq import ChatGroq
# from src.config.settings import settings
# from src.control.agents.merge_node.prompts import (
#     build_merge_messages,
#     build_system_prompt,
# )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MAX_MERGE_RETRIES = 2

DATE_FORMATS = [
    "%Y-%m-%d",
    "%d-%b-%Y",
    "%d/%m/%y",
    "%d/%m/%Y",
]
PARTIAL_DATE_FORMATS = ["%d-%b", "%d-%B", "%b-%d", "%B-%d"]


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def _to_decimal(value: Any) -> Decimal | None:
    if _is_missing(value):
        return None
    try:
        return Decimal(str(value).strip())
    except Exception:
        return None


def _nearest_year_date(month: int, day: int, reference_date: date) -> date | None:
    candidates: list[date] = []
    for year in (reference_date.year - 1, reference_date.year, reference_date.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            continue
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: abs(candidate - reference_date))


def _parse_date_value(value: Any, reference_date: date | None = None) -> date | None:
    if _is_missing(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    if reference_date is not None:
        for fmt in PARTIAL_DATE_FORMATS:
            try:
                parsed = datetime.strptime(text, fmt).date()
            except ValueError:
                continue
            return _nearest_year_date(parsed.month, parsed.day, reference_date)

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
            check_in = timesheet_record.get("check_in")
            check_out = timesheet_record.get("check_out")
            derived_hours = _duration_hours(check_in, check_out)

            if hours is None and derived_hours is not None:
                timesheet_record["hours"] = str(derived_hours)
                continue

            if (
                hours is not None
                and derived_hours is not None
                and abs(hours - derived_hours) > Decimal("0.05")
            ):
                logger.warning(
                    "Hour conflict detected for employee %s on %s: hours=%s derived=%s",
                    record.get("employee_name", "unknown"),
                    timesheet_record.get("date", "unknown"),
                    hours,
                    derived_hours,
                )

    return records


_WEEKDAY_OFFSETS = {
    "monday": -6,
    "mon": -6,
    "tuesday": -5,
    "tue": -5,
    "wednesday": -4,
    "wed": -4,
    "thursday": -3,
    "thu": -3,
    "friday": -2,
    "fri": -2,
    "saturday": -1,
    "sat": -1,
    "sunday": 0,
    "sun": 0,
}


def _normalize_weekday_dates(
    records: list[dict[str, Any]],
    week_ending: date | None,
) -> list[dict[str, Any]]:
    """Normalize date/day pairs, using week ending only when date is absent."""
    for employee_record in records:
        timesheet_records = employee_record.get("timesheet_records") or []
        if not isinstance(timesheet_records, list):
            continue

        for timesheet_record in timesheet_records:
            if not isinstance(timesheet_record, dict):
                continue

            parsed_date = _parse_date_value(timesheet_record.get("date"), week_ending)
            if parsed_date is not None:
                timesheet_record["date"] = str(parsed_date)
                timesheet_record["day"] = parsed_date.strftime("%A")
                continue

            day_value = timesheet_record.get("day")
            if not isinstance(day_value, str):
                timesheet_record["date"] = None
                continue

            weekday_offset = _WEEKDAY_OFFSETS.get(day_value.strip().lower())
            if weekday_offset is None:
                timesheet_record["date"] = None
                continue

            if week_ending is None:
                timesheet_record["date"] = None
            else:
                calculated_date = week_ending + timedelta(days=weekday_offset)
                timesheet_record["date"] = str(calculated_date)
                timesheet_record["day"] = calculated_date.strftime("%A")

    return records


def _is_merge_response_payload(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("global_data"), dict)
        and isinstance(value.get("employee_records"), list)
    )


def _iter_raw_merge_payloads(payload: Any) -> Iterator[dict[str, Any]]:
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

    trace_payload = payload.get("payload")
    if trace_payload is not None:
        yield from _iter_raw_merge_payloads(trace_payload)


def _load_extracted_merge_payloads(
    extracted_data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for source_index, source in enumerate(extracted_data, start=1):
        payload = source.get("extracted_payload")
        for raw_payload in _iter_raw_merge_payloads(payload):
            try:
                payloads.append(MergeResponse.model_validate(raw_payload).model_dump())
            except Exception as exc:
                logger.warning(
                    "Skipping invalid extracted payload from source %d (%s): %s",
                    source_index,
                    source.get("attachment_name", "unknown"),
                    exc,
                )
    return payloads


def _first_present(current: Any, incoming: Any) -> Any:
    if not _is_missing(current):
        return current
    if _is_missing(incoming):
        return current
    return incoming


def _employee_key(employee_name: Any) -> str:
    normalized = str(employee_name or "").translate(
        dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)
    )
    return " ".join(normalized.lower().split())


def _format_decimal(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(value.quantize(Decimal("1")))
    return format(value.normalize(), "f")


def _best_total_hours(current: Any, incoming: Any) -> Any:
    if _is_missing(current):
        return incoming if not _is_missing(incoming) else current
    if _is_missing(incoming):
        return current

    current_decimal = _to_decimal(current)
    incoming_decimal = _to_decimal(incoming)
    if current_decimal is None or incoming_decimal is None:
        return current
    return _format_decimal(max(current_decimal, incoming_decimal))


def _timesheet_record_key(record: dict[str, Any]) -> tuple[str, str] | None:
    date_value = record.get("date")
    if not _is_missing(date_value):
        return ("date", str(date_value).strip().lower())

    day_value = record.get("day")
    if not _is_missing(day_value):
        return ("day", str(day_value).strip().lower())

    return None


def _merge_timesheet_record(
    existing: dict[str, Any],
    incoming: dict[str, Any],
) -> dict[str, Any]:
    for field, incoming_value in incoming.items():
        existing_value = existing.get(field)
        if _is_missing(existing_value) and not _is_missing(incoming_value):
            existing[field] = incoming_value
            continue

        if field == "confidence" and incoming_value is not None:
            try:
                existing[field] = max(float(existing_value or 0), float(incoming_value))
            except (TypeError, ValueError):
                pass

    return existing


def _compact_timesheet_records(records: list[Any]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    records_by_key: dict[tuple[str, str], dict[str, Any]] = {}

    for record in records:
        if not isinstance(record, dict):
            continue

        key = _timesheet_record_key(record)
        if key is None:
            compacted.append(record)
            continue

        if key in records_by_key:
            _merge_timesheet_record(records_by_key[key], record)
            continue

        record_copy = dict(record)
        records_by_key[key] = record_copy
        compacted.append(record_copy)

    return compacted


def _sum_timesheet_record_hours(records: list[dict[str, Any]]) -> Decimal | None:
    total = Decimal("0")
    has_hours = False

    for record in records:
        hours = _to_decimal(record.get("hours"))
        if hours is None:
            continue
        total += hours
        has_hours = True

    return total if has_hours else None


def _finalize_employee_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for employee_record in records:
        timesheet_records = _compact_timesheet_records(
            employee_record.get("timesheet_records") or []
        )
        employee_record["timesheet_records"] = timesheet_records

        daily_total = _sum_timesheet_record_hours(timesheet_records)
        existing_total = _to_decimal(employee_record.get("total_hours"))
        if daily_total is not None and (
            existing_total is None or daily_total > existing_total
        ):
            employee_record["total_hours"] = _format_decimal(daily_total)

    return records


def _merge_source_lists(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen = {
        (
            str(source.get("file_name") or ""),
            str(source.get("content_type") or ""),
        )
        for source in existing
        if isinstance(source, dict)
    }
    for source in incoming:
        if not isinstance(source, dict):
            continue
        key = (
            str(source.get("file_name") or ""),
            str(source.get("content_type") or ""),
        )
        if key in seen:
            continue
        existing.append(source)
        seen.add(key)
    return existing


def _combine_merge_payloads(extracted_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    combined: dict[str, Any] = {
        "global_data": {
            "client_name": None,
            "week_ending": None,
            "department": None,
        },
        "employee_records": [],
    }
    employees_by_key: dict[str, dict[str, Any]] = {}

    for payload in extracted_payloads:
        global_data = payload.get("global_data") or {}
        combined_global_data = combined["global_data"]
        combined_global_data["client_name"] = _first_present(
            combined_global_data.get("client_name"),
            global_data.get("client_name"),
        )
        combined_global_data["week_ending"] = _first_present(
            combined_global_data.get("week_ending"),
            global_data.get("week_ending"),
        )
        combined_global_data["department"] = _first_present(
            combined_global_data.get("department"),
            global_data.get("department"),
        )

        for employee_record in payload.get("employee_records") or []:
            employee_name = employee_record.get("employee_name")
            key = _employee_key(employee_name)
            if not key:
                continue

            if key not in employees_by_key:
                employees_by_key[key] = {
                    "employee_name": employee_name,
                    "department": employee_record.get("department"),
                    "total_hours": employee_record.get("total_hours"),
                    "source": list(employee_record.get("source") or []),
                    "timesheet_records": list(employee_record.get("timesheet_records") or []),
                }
                continue

            existing = employees_by_key[key]
            existing["department"] = _first_present(
                existing.get("department"),
                employee_record.get("department"),
            )
            existing["total_hours"] = _best_total_hours(
                existing.get("total_hours"),
                employee_record.get("total_hours"),
            )
            existing["source"] = _merge_source_lists(
                existing.get("source") or [],
                list(employee_record.get("source") or []),
            )
            existing_timesheet_records = existing.get("timesheet_records") or []
            existing_timesheet_records.extend(
                list(employee_record.get("timesheet_records") or [])
            )
            existing["timesheet_records"] = existing_timesheet_records

    global_department = combined["global_data"].get("department")
    if not _is_missing(global_department):
        for employee_record in employees_by_key.values():
            if _is_missing(employee_record.get("department")):
                employee_record["department"] = global_department

    combined["employee_records"] = _finalize_employee_records(list(employees_by_key.values()))
    return MergeResponse.model_validate(combined).model_dump()


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
        extracted_payloads = _load_extracted_merge_payloads(extracted_data)
        if not extracted_payloads:
            raise ValueError("No structured extraction payloads available for merge")

        payload = _combine_merge_payloads(extracted_payloads)

        # Step 3: Store result as JSON file for testing
        # trace_path = store_llm_result_for_testing(
        #     source="merge",
        #     payload=payload,
        #     extra={
        #         "email_id": str(email_id),
        #         "source_count": len(extracted_data),
        #         "structured_payload_count": len(extracted_payloads),
        #     },
        # )
        # logger.info("Stored merge result for testing at %s", trace_path)

        # Step 4: Extract client_name and week_ending from payload
        global_data = payload.get("global_data", {})
        client_name = global_data.get("client_name")
        week_ending_str = global_data.get("week_ending")
        week_ending = None

        if week_ending_str:
            for fmt in DATE_FORMATS:
                try:
                    week_ending = datetime.strptime(week_ending_str, fmt).date()
                    break
                except ValueError:
                    continue

        if week_ending_str and week_ending is None:
            logger.warning(
                "Failed to parse week_ending '%s' for email %s",
                week_ending_str,
                email_id,
            )
        payload["employee_records"] = _normalize_weekday_dates(
            payload.get("employee_records", []),
            week_ending,
        )
        payload["employee_records"] = _calculate_hours_from_check_in_out(
            payload.get("employee_records", [])
        )
        payload["employee_records"] = _finalize_employee_records(
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
            len(extracted_payloads),
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
        # store_llm_result_for_testing(
        #     source="merge",
        #     payload={
        #         "success": False,
        #         "error": str(e),
        #         "email_id": str(email_id),
        #         "source_count": len(extracted_data),
        #     },
        #     extra={"email_id": str(email_id)},
        # )

        return state
