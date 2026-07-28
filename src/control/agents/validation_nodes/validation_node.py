from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from sqlalchemy import select

from src.control.agents.graph_config import get_db_session
from src.control.agents.state import TimeguardState
from src.data.models.assignments import Assignment
from src.data.models.client_rules import ClientRule
from src.data.models.email import EmailStatus
from src.data.models.exception import ExceptionSeverity, ExceptionType
from src.data.models.timecard import ExceptionSeverity as TimecardSeverity
from src.data.models.timecard import TimecardStatus
from src.data.models.timesheet import TimesheetStatus
from src.data.repositories.email_repository import EmailRepository
from src.data.repositories.exception_repository import ExceptionRepository
from src.data.repositories.timecard_repository import TimecardRepository
from src.data.repositories.timesheet_repository import TimesheetRepository

logger = logging.getLogger(__name__)

DAILY_HOURS_LIMIT = Decimal("15")
WEEKLY_HOURS_LIMIT = Decimal("75")
DURATION_TOLERANCE_HOURS = Decimal("0.05")
ValidationFailure = tuple[ExceptionType, ExceptionSeverity, dict[str, Any] | None]


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def _to_decimal(value: Any) -> Decimal | None:
    if _is_missing(value):
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def _duration_value_hours(value: Any) -> Decimal | None:
    decimal_value = _to_decimal(value)
    if decimal_value is not None:
        return decimal_value
    if _is_missing(value):
        return None

    text = str(value).strip()
    parts = text.split(":")
    if len(parts) not in {2, 3}:
        return None

    try:
        hours = Decimal(parts[0].strip() or "0")
        minutes = Decimal(parts[1].strip() or "0")
        seconds = Decimal(parts[2].strip() or "0") if len(parts) == 3 else Decimal("0")
    except (InvalidOperation, ValueError):
        return None

    if minutes < 0 or minutes >= 60 or seconds < 0 or seconds >= 60:
        return None

    return (hours + (minutes / Decimal("60")) + (seconds / Decimal("3600"))).quantize(
        Decimal("0.01")
    )


def _uuid_or_none(value: Any) -> UUID | None:
    if _is_missing(value):
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if _is_missing(value):
        return None

    text = str(value).strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_time(value: Any) -> datetime | None:
    if _is_missing(value):
        return None

    text = str(value).strip()
    try:
        return datetime.strptime(text, "%H:%M")
    except ValueError:
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


def _record_hours(record: dict[str, Any]) -> Decimal | None:
    hours = _to_decimal(record.get("hours"))
    if hours is not None:
        return hours
    return _duration_hours(record.get("check_in"), record.get("check_out"))


def _record_break_hours(record: dict[str, Any], rule: ClientRule | None) -> Decimal:
    payload_break = _duration_value_hours(record.get("break_hour"))
    if payload_break is None:
        payload_break = _duration_value_hours(record.get("break_hours"))
    if payload_break is not None:
        return payload_break
    if rule is not None and rule.break_auto_deduct and rule.break_deduction_hrs is not None:
        return Decimal(rule.break_deduction_hrs)
    return Decimal("0")


def _week_ending_from_payload(payload: dict[str, Any], fallback: date | None) -> date | None:
    global_data = payload.get("global_data") or {}
    parsed = _parse_date(global_data.get("week_ending"))
    if parsed is not None:
        return parsed
    return fallback


def _exception_reason(
    exc_type: ExceptionType,
    employee_name: str | None,
    record: dict[str, Any] | None = None,
) -> str:
    prefix = employee_name or "Unknown employee"
    record_data = record or {}
    date_label = f" on {record_data['date']}" if record_data.get("date") else ""

    if exc_type == ExceptionType.MISSING_TIME_ENTRY:
        missing_fields: list[str] = []
        if _is_missing(record_data.get("check_in")):
            missing_fields.append("check-in")
        if _is_missing(record_data.get("check_out")):
            missing_fields.append("check-out")
        if not missing_fields:
            missing_fields.append("time entry")
        fields = " and ".join(missing_fields)
        return (
            f"{prefix}{date_label} is missing {fields}. "
            "Add the missing time value or enter total hours."
        )

    if exc_type == ExceptionType.LOW_CONFIDENCE:
        confidence = record_data.get("confidence")
        if not _is_missing(confidence):
            return (
                f"{prefix}{date_label} has low extraction confidence ({confidence}). "
                "Review the extracted row before approval."
            )
        return (
            f"{prefix}{date_label} has low extraction confidence. "
            "Review the extracted row before approval."
        )

    if exc_type == ExceptionType.MISSING_CLIENT:
        return (
            "Client could not be matched from the extracted client name or sender "
            "email. Select the correct client."
        )

    if exc_type == ExceptionType.MISSING_WEEK_ENDING:
        return (
            "Week ending is missing or could not be parsed from the timesheet. "
            "Enter the correct week ending date."
        )

    if exc_type == ExceptionType.MISSING_DEPARTMENT:
        return (
            f"{prefix} has a missing or unmatched department. Select a department "
            "assigned to the resolved client."
        )

    if exc_type == ExceptionType.MISSING_EMPLOYEE_ID:
        return (
            f"{prefix} could not be matched to an active employee. Correct the "
            "employee name for the resolved client and department."
        )

    if exc_type == ExceptionType.MISSING_ASSIGNMENT_ID:
        return (
            f"{prefix} matched an employee, but no assignment was found for the "
            "resolved client and department. Assign the employee before approval."
        )

    if exc_type == ExceptionType.TIME_ENTRY_CONFLICT:
        if record_data:
            recorded_hours = _to_decimal(record_data.get("hours"))
            derived_hours = _duration_hours(
                record_data.get("check_in"),
                record_data.get("check_out"),
            )
            if recorded_hours is not None and derived_hours is not None:
                return (
                    f"{prefix}{date_label} has {recorded_hours} recorded hours, "
                    f"but check-in/check-out calculate to {derived_hours} hours. "
                    "Correct the time or hours."
                )
            return (
                f"{prefix}{date_label} has conflicting check-in, check-out, or "
                "hours values. Correct the time entry."
            )
        return (
            f"{prefix}'s employee total hours do not match the sum of daily time "
            "entries. Correct the total hours or daily rows."
        )

    if exc_type == ExceptionType.HOURS_EXCEED_LIMIT:
        record_hours = _record_hours(record_data)
        if record_hours is not None:
            return (
                f"{prefix}{date_label} has {record_hours} hours, which exceeds "
                f"the {DAILY_HOURS_LIMIT}-hour daily limit."
            )
        return f"{prefix}{date_label} exceeds the {DAILY_HOURS_LIMIT}-hour daily limit."

    if exc_type == ExceptionType.WEEKLY_HOURS_EXCEED_LIMIT:
        return f"{prefix}'s weekly hours exceed the {WEEKLY_HOURS_LIMIT}-hour weekly limit."

    if exc_type == ExceptionType.CALCULATION_DISCREPANCY:
        return (
            f"{prefix}{date_label} has a payroll calculation discrepancy. "
            "Recalculate the timecard before approval."
        )

    return (
        f"{prefix} has an unsupported validation exception: {exc_type.value}. "
        "Review the timecard details."
    )


def _severity_rank(severity: ExceptionSeverity) -> int:
    return {
        ExceptionSeverity.NONE: 0,
        ExceptionSeverity.LOW: 1,
        ExceptionSeverity.MEDIUM: 2,
        ExceptionSeverity.HIGH: 3,
    }[severity]


def _max_severity(severities: list[ExceptionSeverity]) -> ExceptionSeverity:
    if not severities:
        return ExceptionSeverity.NONE
    return max(severities, key=_severity_rank)


def _matching_failures(
    employee: dict[str, Any],
    week_ending: date | None,
) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []
    if week_ending is None:
        failures.append((ExceptionType.MISSING_WEEK_ENDING, ExceptionSeverity.HIGH, {}))
    if employee.get("client_match_failed"):
        failures.append((ExceptionType.MISSING_CLIENT, ExceptionSeverity.HIGH, {}))
    if employee.get("department_match_failed"):
        failures.append((ExceptionType.MISSING_DEPARTMENT, ExceptionSeverity.HIGH, {}))
    return failures


def _validate_employee_record(employee: dict[str, Any]) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []
    records = list(employee.get("timesheet_records") or [])
    employee_total_hours = _to_decimal(employee.get("total_hours"))

    if _is_missing(employee.get("emp_id")):
        failures.append((ExceptionType.MISSING_EMPLOYEE_ID, ExceptionSeverity.HIGH, {}))
        # Skip other validations if emp_id is missing
        return failures

    if _is_missing(employee.get("assignment_id")):
        failures.append((ExceptionType.MISSING_ASSIGNMENT_ID, ExceptionSeverity.HIGH, {}))

    weekly_total = Decimal("0")
    for record in records:
        check_in = record.get("check_in")
        check_out = record.get("check_out")
        hours = _to_decimal(record.get("hours"))
        has_check_in = not _is_missing(check_in)
        has_check_out = not _is_missing(check_out)

        # If hours not given but check_in and check_out are given, calculate and store hours
        # if hours is None and not _is_missing(check_in) and not _is_missing(check_out):
        #     calculated_hours = _duration_hours(check_in, check_out)
        #     if calculated_hours is not None:
        #         record["hours"] = str(calculated_hours)
        #         hours = calculated_hours

        effective_hours = hours if hours is not None else None
        derived_hours = _duration_hours(check_in, check_out)

        # has_valid_time = (
        #     hours is not None
        #     or employee_total_hours is not None
        #     or (has_check_in and has_check_out)
        # )
        if has_check_in ^ has_check_out:
            failures.append(
                (ExceptionType.MISSING_TIME_ENTRY, ExceptionSeverity.MEDIUM, record)
            )
        # logger.info(
        #     f"has_valid_time: {has_valid_time} ,check_in:{check_in} ,check_out:{check_out}"
        # )
        # if not has_valid_time:
        #     failures.append(
        #         (ExceptionType.MISSING_TIME_ENTRY, ExceptionSeverity.MEDIUM, record)
        #     )

        confidence = _to_decimal(record.get("confidence"))
        if confidence is not None and Decimal("0") < confidence <= Decimal("0.6"):
            failures.append((ExceptionType.LOW_CONFIDENCE, ExceptionSeverity.LOW, record))

        if derived_hours is not None and effective_hours is not None:
            if abs(derived_hours - effective_hours) > DURATION_TOLERANCE_HOURS:
                failures.append(
                    (
                        ExceptionType.TIME_ENTRY_CONFLICT,
                        ExceptionSeverity.MEDIUM,
                        record,
                    )
                )

        record_hours = effective_hours if effective_hours is not None else derived_hours
        if record_hours is not None:
            weekly_total += record_hours
            if record_hours > DAILY_HOURS_LIMIT:
                failures.append(
                    (ExceptionType.HOURS_EXCEED_LIMIT, ExceptionSeverity.HIGH, record)
                )
    if weekly_total == Decimal("0") and employee_total_hours is not None:
        weekly_total = employee_total_hours
    if (
        employee_total_hours is not None
        and abs(employee_total_hours - weekly_total) > DURATION_TOLERANCE_HOURS
    ):
        failures.append((ExceptionType.TIME_ENTRY_CONFLICT, ExceptionSeverity.MEDIUM, None))
    if weekly_total > WEEKLY_HOURS_LIMIT or (
        employee_total_hours is not None and employee_total_hours > WEEKLY_HOURS_LIMIT
    ):
        failures.append(
            (ExceptionType.WEEKLY_HOURS_EXCEED_LIMIT, ExceptionSeverity.HIGH, None)
        )
    return failures


async def _get_rule_for_assignment(
    db_session: Any,
    assignment_id: Any,
) -> ClientRule | None:
    assignment_uuid = _uuid_or_none(assignment_id)
    if assignment_uuid is None:
        return None

    result = await db_session.execute(
        select(ClientRule)
        .join(Assignment, Assignment.department_id == ClientRule.department_id)
        .where(
            Assignment.assignment_id == assignment_uuid,
            ClientRule.client_id == Assignment.client_id,
            ClientRule.is_active.is_(True),
        )
    )
    rule = result.scalar_one_or_none()
    return rule if isinstance(rule, ClientRule) else None


def _split_hours(
    total_hours: Decimal,
    rule: ClientRule | None,
) -> tuple[Decimal, Decimal, Decimal]:
    if rule is None:
        return total_hours, Decimal("0"), Decimal("0")

    ot_threshold = Decimal(rule.weekly_ot_threshold)
    dt_threshold = (
        Decimal(rule.weekly_dt_threshold)
        if rule.weekly_dt_threshold is not None
        else total_hours
    )
    #  if rule is not None and rule.weekly_dt_threshold is not None
    # else None

    if total_hours <= ot_threshold:
        return total_hours, Decimal("0"), Decimal("0")

    reg_hours = ot_threshold
    if total_hours <= dt_threshold:
        return reg_hours, total_hours - ot_threshold, Decimal("0")

    return reg_hours, dt_threshold - ot_threshold, total_hours - dt_threshold


def _payable_weekly_hours(
    employee: dict[str, Any],
    rule: ClientRule | None,
) -> Decimal:
    total = Decimal("0")
    has_row_hours = False
    for record in list(employee.get("timesheet_records") or []):
        hours = _record_hours(record)
        if hours is None:
            continue
        has_row_hours = True
        break_hours = _record_break_hours(record, rule)
        total += max(Decimal("0"), hours - break_hours)

    if has_row_hours:
        return total.quantize(Decimal("0.01"))

    employee_total_hours = _to_decimal(employee.get("total_hours"))
    if employee_total_hours is None:
        return total.quantize(Decimal("0.01"))

    if rule is not None and rule.break_auto_deduct and rule.break_deduction_hrs is not None:
        break_hours = Decimal(rule.break_deduction_hrs) * Decimal("5")
        employee_total_hours = max(Decimal("0"), employee_total_hours - break_hours)
    logger.info(
        f"Employee {employee.get('employee_name')} has no row-level hours,"
        f" using total_hours={employee_total_hours}"
    )
    return employee_total_hours.quantize(Decimal("0.01"))


async def validation_node(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    db_session = get_db_session(config)
    email_id = state.get("email_id")
    if not email_id:
        logger.warning("Skipping validation because state.email_id is missing")
        return state

    try:
        exception_repository = ExceptionRepository(db_session)
        timecard_repository = TimecardRepository(db_session)
        timesheet_repository = TimesheetRepository(db_session)
        email_repository = EmailRepository(db_session)
        timesheet = await timesheet_repository.get_by_email_id(email_id=email_id)
        if timesheet is None or not isinstance(timesheet.payload, dict):
            logger.warning(
                "Skipping validation because payload is missing for email %s",
                email_id,
            )
            return state

        payload = timesheet.payload
        employee_records = list(payload.get("employee_records") or [])
        week_ending = _week_ending_from_payload(payload, timesheet.week_ending)

        await timecard_repository.delete_by_timesheet(timesheet.timesheet_id)

        for employee in employee_records:
            employee_name = employee.get("employee_name")
            matching_failures = _matching_failures(employee, week_ending)
            blocks_employee_matching = any(
                exc_type in {ExceptionType.MISSING_CLIENT, ExceptionType.MISSING_DEPARTMENT}
                for exc_type, _, _ in matching_failures
            )
            failures = list(matching_failures)
            if not blocks_employee_matching:
                failures.extend(_validate_employee_record(employee))
            severities = [severity for _, severity, _ in failures]
            status = TimecardStatus.EXCEPTION if failures else TimecardStatus.NO_EXCEPTION
            severity = _max_severity(severities)

            # Skip calculations if emp_id is missing
            emp_id_missing = any(
                exc_type == ExceptionType.MISSING_EMPLOYEE_ID for exc_type, _, _ in failures
            )

            if emp_id_missing:
                # Create timecard with null hours when emp_id is missing
                timecard = await timecard_repository.create_generated_timecard(
                    timesheet_id=timesheet.timesheet_id,
                    emp_id=_uuid_or_none(employee.get("emp_id")),
                    assignment_id=_uuid_or_none(employee.get("assignment_id")),
                    rule_id=None,
                    week_ending=week_ending,
                    employee_name=employee_name,
                    reg_hours=None,
                    ot_hours=None,
                    dt_hours=None,
                    status=status,
                    severity=TimecardSeverity(severity.value),
                )
            else:
                # Normal calculation flow when emp_id is present
                rule = await _get_rule_for_assignment(
                    db_session, employee.get("assignment_id")
                )
                payable_hours = _payable_weekly_hours(employee, rule)
                reg_hours, ot_hours, dt_hours = _split_hours(payable_hours, rule)

                timecard = await timecard_repository.create_generated_timecard(
                    timesheet_id=timesheet.timesheet_id,
                    emp_id=_uuid_or_none(employee.get("emp_id")),
                    assignment_id=_uuid_or_none(employee.get("assignment_id")),
                    rule_id=rule.rule_id if rule is not None else None,
                    week_ending=week_ending,
                    employee_name=employee_name,
                    reg_hours=reg_hours,
                    ot_hours=ot_hours,
                    dt_hours=dt_hours,
                    status=status,
                    severity=TimecardSeverity(severity.value),
                )
            exception_entries = [
                (
                    exc_severity,
                    exc_type,
                    _exception_reason(exc_type, employee_name, record),
                )
                for exc_type, exc_severity, record in failures
            ]
            await exception_repository.create_many_for_timecard(
                timecard_id=timecard.timecard_id,
                entries=exception_entries,
            )

        timesheet.status = TimesheetStatus.UNDER_REVIEW

        # Update email status to indicate successful validation
        email = await email_repository.get_by_id(email_id)
        if email:
            await email_repository.set_status(email, EmailStatus.PROCESSED)
            logger.info(
                "Email %s status updated to PROCESSED    after successful validation", email_id
            )

        await db_session.commit()
        logger.info("Validation completed for email %s", email_id)
        return state

    except Exception as e:
        logger.error("Validation failed for email %s: %s", email_id, e)

        # Update email status to FAILED with failure stage and reason
        email_repository = EmailRepository(db_session)
        email = await email_repository.get_by_id(email_id)
        if email:
            await email_repository.set_status(
                email,
                EmailStatus.FAILED,
                failure_stage="validation",
                failure_reason=str(e),
            )
            logger.info("Set email %s status to FAILED with stage 'validation'", email_id)

        await db_session.commit()
        raise e
