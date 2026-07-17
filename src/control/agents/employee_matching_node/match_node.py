from __future__ import annotations

import copy
import logging
import re
import unicodedata
from datetime import date, datetime
from email.utils import parseaddr
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from rapidfuzz import fuzz
from scipy.optimize import linear_sum_assignment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.control.agents.graph_config import get_db_session
from src.control.agents.state import TimeguardState
from src.data.models.assignments import Assignment, AssignmentStatus
from src.data.models.clients import Client
from src.data.models.department import Department
from src.data.models.email import EmailStatus
from src.data.models.employee import Employee
from src.data.models.timesheet import TimesheetStatus
from src.data.repositories.client_repository import ClientRepository
from src.data.repositories.department_repository import DepartmentRepository
from src.data.repositories.email_repository import EmailRepository
from src.data.repositories.timesheet_repository import TimesheetRepository

# from src.llm_trace_debug import store_llm_result_for_testing

logger = logging.getLogger(__name__)

MIN_MATCHING_SCORE = 85.0
NON_MATCH_COST = 1_000_000.0
DATE_FORMATS = ("%Y-%m-%d", "%d-%b-%Y", "%d/%m/%y", "%d/%m/%Y")


def _is_missing(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _parse_week_ending(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if _is_missing(value):
        return None

    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_name(value: str | None) -> str:
    if not value:
        return ""

    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def get_client_matching_score(a: str, b: str) -> float:
    return max(
        fuzz.ratio(a, b),
        fuzz.token_sort_ratio(a, b),
        fuzz.token_set_ratio(a, b),
        fuzz.partial_ratio(a, b),
    )


def _extract_sender_email(sender_mail: str | None) -> str | None:
    if not sender_mail:
        return None

    _, parsed_email = parseaddr(sender_mail)
    if parsed_email:
        return parsed_email.strip().lower()

    normalized = sender_mail.strip().lower()
    return normalized or None


def _extract_sender_domain(sender_email: str | None) -> str | None:
    if not sender_email or "@" not in sender_email:
        return None

    domain = sender_email.rsplit("@", 1)[-1].strip().lower()
    return domain or None


async def _resolve_client_and_department(
    state: TimeguardState,
    config: RunnableConfig,
) -> tuple[Client | None, Department | None]:
    payload = state.get("payload") or {}
    global_data = payload.get("global_data") or {}
    client_name = (global_data.get("client_name") or "").strip() or None
    department_name = (global_data.get("department") or "").strip() or None

    db_session = get_db_session(config)
    client_repository = ClientRepository(db_session)

    client: Client | None = None
    if client_name:
        # Get all active clients for fuzzy matching
        all_clients = await client_repository.get_active_clients()

        if all_clients:
            # Perform fuzzy matching to find the best client match
            best_client = None
            best_score = 0.0

            normalized_client_name = _normalize_name(client_name)

            for db_client in all_clients:
                normalized_db_name = _normalize_name(db_client.client_name)
                score = get_client_matching_score(
                    normalized_client_name,
                    normalized_db_name,
                )

                if score >= MIN_MATCHING_SCORE and score > best_score:
                    best_score = score
                    best_client = db_client

            if best_client:
                client = best_client
                logger.info(
                    "Fuzzy matched client '%s' to DB client '%s' with score %.2f",
                    client_name,
                    client.client_name,
                    best_score,
                )
            else:
                logger.warning(
                    "No fuzzy match found for client '%s' (best score: %.2f)",
                    client_name,
                    best_score,
                )
    else:
        sender_email = _extract_sender_email(state.get("sender_mail"))
        if sender_email:
            client = await client_repository.get_by_sender_email(sender_email)
            if client is None:
                sender_domain = _extract_sender_domain(sender_email)
                if sender_domain:
                    client = await client_repository.get_by_sender_domain(sender_domain)

    if client is None:
        return None, None

    department: Department | None = None
    if department_name:
        result = await db_session.execute(
            select(Department).where(
                Department.client_id == client.client_id,
                Department.department_name == department_name,
                Department.is_active.is_(True),
            )
        )
        department = result.scalar_one_or_none()

    return client, department


async def _get_candidate_employees(
    db_session: AsyncSession,
    client: Client,
) -> list[dict[str, Any]]:
    stmt = (
        select(Assignment, Employee, Department)
        .join(Employee, Employee.emp_id == Assignment.emp_id)
        .join(Department, Department.department_id == Assignment.department_id)
        .where(
            Assignment.status == AssignmentStatus.ACTIVE,
            Assignment.client_id == client.client_id,
            Employee.is_active.is_(True),
            Department.is_active.is_(True),
        )
    )

    result = await db_session.execute(stmt)
    candidates: list[dict[str, Any]] = []
    for assignment, employee, department_row in result.all():
        candidates.append(
            {
                "emp_id": str(employee.emp_id),
                "employee_name": employee.name,
                "assignment_id": str(assignment.assignment_id),
                "department": department_row.department_name,
            }
        )

    return candidates


async def _fuzzy_match_department(
    extracted_department: str,
    db_departments: list[Department],
) -> Department | None:
    """Fuzzy match extracted department name against database departments."""
    if not extracted_department or not db_departments:
        return None

    best_department = None
    best_score = 0.0
    normalized_extracted = _normalize_name(extracted_department)

    for db_dept in db_departments:
        normalized_db_name = _normalize_name(db_dept.department_name)
        score = get_client_matching_score(normalized_extracted, normalized_db_name)

        if score >= MIN_MATCHING_SCORE and score > best_score:
            best_score = score
            best_department = db_dept

    if best_department:
        logger.info(
            "Fuzzy matched department '%s' to DB department '%s' with score %.2f",
            extracted_department,
            best_department.department_name,
            best_score,
        )
    else:
        logger.warning(
            "No fuzzy match found for department '%s' (best score: %.2f)",
            extracted_department,
            best_score,
        )

    return best_department


def _build_similarity_matrix(
    extracted_names: list[str],
    candidate_names: list[str],
) -> list[list[float]]:
    matrix: list[list[float]] = []
    for extracted_name in extracted_names:
        extracted_normalized = _normalize_name(extracted_name)
        row: list[float] = []
        for candidate_name in candidate_names:
            candidate_normalized = _normalize_name(candidate_name)
            row.append(
                float(
                    fuzz.token_sort_ratio(
                        extracted_normalized,
                        candidate_normalized,
                    )
                )
            )
        matrix.append(row)
    return matrix


def _match_employees(
    extracted_records: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not extracted_records:
        return []

    enriched_records = [copy.deepcopy(record) for record in extracted_records]
    for record in enriched_records:
        record["extracted_employee_name"] = record.get(
            "extracted_employee_name"
        ) or record.get("employee_name")

    if not candidates:
        for record in enriched_records:
            record["emp_id"] = None
            record["assignment_id"] = None
            record["matching_score"] = None
            record["employee_matching_score"] = None
        return enriched_records

    similarity_matrix = _build_similarity_matrix(
        [record.get("employee_name", "") for record in enriched_records],
        [candidate["employee_name"] for candidate in candidates],
    )

    cost_matrix: list[list[float]] = []
    for row_index, row in enumerate(similarity_matrix):
        cost_row = []
        extracted_department = enriched_records[row_index].get("department")
        for col_index, score in enumerate(row):
            # Check if department matches (if specified in extracted record)
            if extracted_department:
                candidate_department = candidates[col_index].get("department")
                if candidate_department and (
                    _normalize_name(extracted_department)
                    != _normalize_name(candidate_department)
                ):
                    # Department mismatch, set high cost
                    cost_row.append(NON_MATCH_COST)
                else:
                    cost_row.append(
                        100.0 - score if score >= MIN_MATCHING_SCORE else NON_MATCH_COST
                    )
            else:
                cost_row.append(
                    100.0 - score if score >= MIN_MATCHING_SCORE else NON_MATCH_COST
                )
        cost_matrix.append(cost_row)

    row_indices, col_indices = linear_sum_assignment(cost_matrix)
    assigned_rows: dict[int, tuple[int, float]] = {}
    for row_index, col_index in zip(
        row_indices,
        col_indices,
        strict=True,
    ):
        score = similarity_matrix[row_index][col_index]
        if score >= MIN_MATCHING_SCORE and cost_matrix[row_index][col_index] < NON_MATCH_COST:
            assigned_rows[row_index] = (col_index, score)

    for row_index, record in enumerate(enriched_records):
        match = assigned_rows.get(row_index)
        if match is None:
            record["emp_id"] = None
            record["assignment_id"] = None
            record["matching_score"] = None
            record["employee_matching_score"] = None
            continue

        candidate_index, score = match
        candidate = candidates[candidate_index]
        matching_score = round(score, 2)
        record["emp_id"] = candidate["emp_id"]
        record["assignment_id"] = candidate["assignment_id"]
        record["matching_score"] = matching_score
        record["employee_matching_score"] = matching_score
        record["employee_name"] = candidate["employee_name"]

    return enriched_records


async def employee_matching_node(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    payload = state.get("payload")
    if not isinstance(payload, dict):
        logger.warning("Skipping employee matching because payload is missing")
        return state

    try:
        global_data = payload.get("global_data") or {}
        client, _department = await _resolve_client_and_department(state, config)

        # Check if client_name was provided but no match found
        # client_name_from_result = (global_data.get("client_name") or "").strip()
        # if client_name_from_result and client is None:
        #     raise ValueError(f"Client name '{client_name_from_result}' does not match
        # any client in the database")

        db_session = get_db_session(config)

        if client is None:
            logger.warning(
                "Continuing with exception rows because client could not be resolved"
            )
            global_data = dict(payload.get("global_data") or {})
            employee_records = [
                dict(record)
                for record in payload.get("employee_records") or []
                if isinstance(record, dict)
            ]
            extracted_client_name = global_data.get("client_name")
            extracted_global_department = global_data.get("department")
            for record in employee_records:
                record["extracted_employee_name"] = record.get(
                    "extracted_employee_name"
                ) or record.get("employee_name")
                record["extracted_client_name"] = extracted_client_name
                extracted_department = record.get("department") or extracted_global_department
                record["extracted_department_name"] = (
                    record.get("extracted_department_name") or extracted_department
                )
                record["client_match_failed"] = True
                if _is_missing(extracted_department):
                    record["department_match_failed"] = True
                record["emp_id"] = None
                record["assignment_id"] = None
                record["matching_score"] = None
                record["employee_matching_score"] = None

            updated_payload = {
                **payload,
                "global_data": global_data,
                "employee_records": employee_records,
            }
            email_id = state.get("email_id")
            if email_id:
                timesheet_repository = TimesheetRepository(db_session)
                timesheet = await timesheet_repository.update_timesheet(
                    email_id=email_id,
                    client_name=str(extracted_client_name).strip()
                    if not _is_missing(extracted_client_name)
                    else None,
                    payload=updated_payload,
                    status=TimesheetStatus.UNDER_REVIEW,
                )
                if timesheet is None:
                    timesheet = await timesheet_repository.create_with_merge_data(
                        email_id=email_id,
                        client_name=str(extracted_client_name).strip()
                        if not _is_missing(extracted_client_name)
                        else None,
                        payload=updated_payload,
                    )
                    timesheet.status = TimesheetStatus.UNDER_REVIEW
            await db_session.commit()
            return cast(TimeguardState, {**state, "payload": updated_payload})

        # Get all active departments for the client for fuzzy matching
        department_repository = DepartmentRepository(db_session)
        all_departments = await department_repository.get_by_client(client.client_id)

        # Fuzzy match department for each extracted employee record before matching
        employee_records = [
            dict(record)
            for record in payload.get("employee_records") or []
            if isinstance(record, dict)
        ]
        extracted_client_name = global_data.get("client_name")
        extracted_global_department = global_data.get("department")
        for record in employee_records:
            extracted_department = record.get("department") or extracted_global_department
            record["extracted_client_name"] = extracted_client_name
            record["extracted_department_name"] = (
                record.get("extracted_department_name") or extracted_department
            )

            if _is_missing(extracted_department):
                record["department"] = None
                record["department_match_failed"] = True
                continue

            # Fuzzy match extracted department with all client departments
            matched_department = await _fuzzy_match_department(
                str(extracted_department), all_departments
            )

            if matched_department:
                # Update department in record
                record["department"] = matched_department.department_name
                record.pop("department_match_failed", None)
                logger.info(
                    "Fuzzy matched department '%s' to '%s' in extracted record",
                    extracted_department,
                    matched_department.department_name,
                )
            else:
                logger.warning(
                    "Could not fuzzy match department '%s'",
                    extracted_department,
                )
                record["department"] = None
                record["department_match_failed"] = True

        # Get all candidates across all departments for the client
        candidates = await _get_candidate_employees(db_session, client)

        global_data = dict(payload.get("global_data") or {})
        global_data["client_name"] = client.client_name

        # if department is not None:
        #     global_data["department"] = department.department_name

        enriched_records = _match_employees(
            employee_records,
            candidates,
        )
        for record in enriched_records:
            if record.get("department_match_failed"):
                record["emp_id"] = None
                record["assignment_id"] = None
                record["matching_score"] = None
                record["employee_matching_score"] = None

        # Calculate hours from check_in/check_out if hours is not provided
        # enriched_records = _calculate_hours_from_check_in_out(enriched_records)

        updated_payload = {
            **payload,
            "global_data": global_data,
            "employee_records": enriched_records,
        }

        # Store payload in timesheet table

        timesheet_repository = TimesheetRepository(db_session)
        email_id = state.get("email_id")
        if email_id:
            await timesheet_repository.update_timesheet(
                email_id=email_id,
                client_name=client.client_name,
                payload=updated_payload,
                status=TimesheetStatus.UNDER_REVIEW,
            )
        await db_session.commit()
        # Store result as JSON file for testing
        # trace_path = store_llm_result_for_testing(
        #     source="employee_matching",
        #     payload=updated_payload,
        #     extra={
        #         "email_id": str(email_id),
        #     },
        # )
        # logger.info("Stored employee matching result for testing at %s", trace_path)

        logger.info("Employee matching completed successfully")
        return cast(
            TimeguardState,
            {
                **state,
                "payload": updated_payload,
            },
        )

    except Exception as e:
        logger.error("Employee matching failed for email %s: %s", state.get("email_id"), e)

        # Update email status to FAILED with failure stage and reason
        db_session = get_db_session(config)
        email_repository = EmailRepository(db_session)
        email_id = state.get("email_id")
        if email_id:
            email = await email_repository.get_by_id(email_id)
            if email:
                await email_repository.set_status(
                    email,
                    EmailStatus.FAILED,
                    failure_stage="employee_matching",
                    failure_reason=str(e),
                )
                logger.info(
                    "Set email %s status to FAILED with stage 'employee_matching'", email_id
                )

        await db_session.commit()
        raise
