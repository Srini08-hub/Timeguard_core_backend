from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Any
from uuid import UUID
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from src.data.models.client import Client

from src.control.agents.employee_matching_node.match_node import (
    MIN_MATCHING_SCORE,
    _fuzzy_match_department,
    _get_candidate_employees,
    _match_employees,
    _normalize_name,
    get_client_matching_score,
)
from src.control.agents.validation_nodes.validation_node import (
    _exception_reason,
    _get_rule_for_assignment,
    _payable_weekly_hours,
    _split_hours,
    _uuid_or_none,
    _validate_employee_record,
    _week_ending_from_payload,
)
from src.core.exceptions.custom_exception import ResourceNotFound, ValidationException
from src.data.models.exception import ExceptionSeverity, ExceptionType
from src.data.models.timecard import ExceptionSeverity as TimecardSeverity
from src.data.models.timecard import Timecard, TimecardStatus
from src.data.models.timesheet import Timesheet, TimesheetStatus
from src.data.repositories.client_repository import ClientRepository
from src.data.repositories.department_repository import DepartmentRepository
from src.data.repositories.email_repository import EmailRepository
from src.data.repositories.exception_repository import ExceptionRepository
from src.data.repositories.timecard_repository import TimecardRepository
from src.data.repositories.timesheet_repository import TimesheetRepository
from src.schemas.timecard_schema import TimecardResponse, TimecardUpdate

MONEY_QUANT = Decimal("0.01")
MATCHING_CORRECTION_TYPES = {
    ExceptionType.MISSING_CLIENT.value,
    ExceptionType.MISSING_WEEK_ENDING.value,
    ExceptionType.MISSING_DEPARTMENT.value,
    ExceptionType.MISSING_EMPLOYEE_ID.value,
}
ValidationFailure = tuple[ExceptionType, ExceptionSeverity, dict[str, Any] | None]


class TimecardService:
    def __init__(
        self,
        timecard_repository: TimecardRepository,
        exception_repository: ExceptionRepository,
        timesheet_repository: TimesheetRepository,
        email_repository: EmailRepository,
    ) -> None:
        self._timecard_repository = timecard_repository
        self._exception_repository = exception_repository
        self._timesheet_repository = timesheet_repository
        self._email_repository = email_repository
        self._db_session = timecard_repository._session

    async def get_timecards_by_timesheet(
        self,
        timesheet_id: UUID,
    ) -> list[TimecardResponse]:
        timecards = await self._timecard_repository.get_by_timesheet(timesheet_id)
        return [self._to_response(timecard) for timecard in timecards]

    async def get_approved_timecards(self) -> list[TimecardResponse]:
        timecards = await self._timecard_repository.get_by_status(TimecardStatus.APPROVED)
        return [self._to_response(timecard) for timecard in timecards]

    async def get_rejected_timecards(self) -> list[TimecardResponse]:
        timecards = await self._timecard_repository.get_by_status(TimecardStatus.REJECTED)
        return [self._to_response(timecard) for timecard in timecards]

    async def get_timecard(self, timecard_id: UUID) -> TimecardResponse:
        timecard = await self._timecard_repository.get_by_id(timecard_id)
        if timecard is None:
            raise ResourceNotFound("Timecard not found")
        return self._to_response(timecard)

    async def approve_timecard(self, timecard_id: UUID) -> TimecardResponse:
        timecard = await self._timecard_repository.get_by_id(timecard_id)
        if timecard is None:
            raise ResourceNotFound("Timecard not found")
        updated = await self._approve_with_payroll(timecard)
        return self._to_response(updated)

    async def approve_timecards(
        self,
        timecard_ids: list[UUID],
    ) -> list[TimecardResponse]:
        approved: list[TimecardResponse] = []
        for timecard_id in timecard_ids:
            timecard = await self._timecard_repository.get_by_id(timecard_id)
            if timecard is None:
                continue
            updated = await self._approve_with_payroll(timecard)
            approved.append(self._to_response(updated))
        return approved

    async def reject_timecard(self, timecard_id: UUID) -> TimecardResponse:
        timecard = await self._timecard_repository.get_by_id(timecard_id)
        if timecard is None:
            raise ResourceNotFound("Timecard not found")
        updated = await self._timecard_repository.reject(timecard)
        return self._to_response(updated)

    async def reject_timecards(
        self,
        timecard_ids: list[UUID],
    ) -> list[TimecardResponse]:
        rejected: list[TimecardResponse] = []
        for timecard_id in timecard_ids:
            timecard = await self._timecard_repository.get_by_id(timecard_id)
            if timecard is None:
                continue
            updated = await self._timecard_repository.reject(timecard)
            rejected.append(self._to_response(updated))
        return rejected

    async def resolve_timecard(
        self,
        timecard_id: UUID,
        payload: TimecardUpdate,
    ) -> TimecardResponse:
        timecard = await self._timecard_repository.get_by_id(timecard_id)
        if timecard is None:
            raise ResourceNotFound("Timecard not found")

        should_process_matching_correction = self._is_matching_correction(timecard)
        if should_process_matching_correction:
            updated = await self._process_matching_correction_timecard(timecard, payload)
            return self._to_response(updated)

        updated = await self._timecard_repository.resolve_with_update(
            timecard,
            employee_name=payload.employee_name,
            week_ending=payload.week_ending,
            reg_hours=payload.reg_hours,
            ot_hours=payload.ot_hours,
            dt_hours=payload.dt_hours,
            review_comment=payload.review_comment,
            reviewed_by=payload.reviewed_by,
        )
        await self._exception_repository.resolve_exceptions(updated.exceptions)
        return self._to_response(updated)

    async def export_approved_timecards(self, week_ending: date) -> bytes:
        timecards = await self._timecard_repository.get_by_status(
            TimecardStatus.APPROVED,
            week_ending=week_ending,
        )
        rows = [
            [
                timecard.employee_name or "",
                timecard.reg_hours or Decimal("0"),
                timecard.ot_hours or Decimal("0"),
                timecard.dt_hours or Decimal("0"),
                timecard.pay_rate or Decimal("0"),
                timecard.regular_pay or Decimal("0"),
                timecard.ot_pay or Decimal("0"),
                timecard.dt_pay or Decimal("0"),
                timecard.gross_pay or Decimal("0"),
            ]
            for timecard in timecards
        ]
        return self._build_xlsx(rows)

    def _is_matching_correction(self, timecard: Timecard) -> bool:
        return any(
            not exception.resolved
            and str(exception.exception_type) in MATCHING_CORRECTION_TYPES
            for exception in timecard.exceptions
        )

    async def _match_client_by_name(self, client_name: str | None) -> Client | None:
        if not client_name:
            return None

        all_clients = await ClientRepository(self._db_session).get_active_clients()
        best_client = None
        best_score = 0.0
        normalized_client_name = _normalize_name(client_name)
        for client in all_clients:
            score = get_client_matching_score(
                normalized_client_name,
                _normalize_name(client.client_name),
            )
            if score >= MIN_MATCHING_SCORE and score > best_score:
                best_score = score
                best_client = client
        return best_client

    @staticmethod
    def _timecard_severity_rank(severity: TimecardSeverity | str) -> int:
        value = str(severity)
        if hasattr(severity, "value"):
            value = severity.value
        return {
            TimecardSeverity.NONE.value: 0,
            TimecardSeverity.LOW.value: 1,
            TimecardSeverity.MEDIUM.value: 2,
            TimecardSeverity.HIGH.value: 3,
        }.get(value, 0)

    async def _clear_week_ending_exceptions_for_timesheet(
        self,
        timesheet_id: UUID,
        week_ending: date | None,
    ) -> None:
        if week_ending is None:
            return

        timecards = await self._timecard_repository.get_by_timesheet(timesheet_id)
        for sibling in timecards:
            sibling.week_ending = week_ending
            missing_week_exceptions = [
                exception
                for exception in sibling.exceptions
                if not exception.resolved
                and str(exception.exception_type) == ExceptionType.MISSING_WEEK_ENDING.value
            ]
            if missing_week_exceptions:
                await self._exception_repository.resolve_exceptions(missing_week_exceptions)

            remaining_exceptions = [
                exception for exception in sibling.exceptions if not exception.resolved
            ]
            if remaining_exceptions:
                sibling.status = TimecardStatus.EXCEPTION
                max_exception = max(
                    remaining_exceptions,
                    key=lambda exception: self._timecard_severity_rank(exception.severity),
                )
                sibling.severity = TimecardSeverity(
                    getattr(max_exception.severity, "value", str(max_exception.severity))
                )
            else:
                sibling.status = TimecardStatus.NO_EXCEPTION
                sibling.severity = TimecardSeverity.NONE
        await self._db_session.flush()

    async def _clear_client_exceptions_for_timesheet(
        self,
        timesheet_id: UUID,
    ) -> None:
        timecards = await self._timecard_repository.get_by_timesheet(timesheet_id)
        for sibling in timecards:
            missing_client_exceptions = [
                exception
                for exception in sibling.exceptions
                if not exception.resolved
                and str(exception.exception_type) == ExceptionType.MISSING_CLIENT.value
            ]
            if missing_client_exceptions:
                await self._exception_repository.resolve_exceptions(missing_client_exceptions)

            remaining_exceptions = [
                exception for exception in sibling.exceptions if not exception.resolved
            ]
            if remaining_exceptions:
                sibling.status = TimecardStatus.EXCEPTION
                max_exception = max(
                    remaining_exceptions,
                    key=lambda exception: self._timecard_severity_rank(exception.severity),
                )
                sibling.severity = TimecardSeverity(
                    getattr(max_exception.severity, "value", str(max_exception.severity))
                )
            else:
                sibling.status = TimecardStatus.NO_EXCEPTION
                sibling.severity = TimecardSeverity.NONE
        await self._db_session.flush()

    async def _process_matching_correction_timecard(
        self,
        timecard: Timecard,
        payload: TimecardUpdate,
    ) -> Timecard:
        timesheet = await self._apply_matching_correction_payload(timecard, payload)
        if not isinstance(timesheet.payload, dict):
            raise ValidationException("Timesheet payload is missing for correction")

        corrected_payload = dict(timesheet.payload)
        global_data = dict(corrected_payload.get("global_data") or {})
        employee_records = [
            dict(record)
            for record in corrected_payload.get("employee_records") or []
            if isinstance(record, dict)
        ]
        target_record = self._find_employee_record(
            employee_records,
            timecard.employee_name,
            payload.employee_name,
        )
        if target_record is None:
            raise ResourceNotFound("Employee row not found for correction")

        client_name = (
            payload.client_name or global_data.get("client_name") or timesheet.client_name
        )
        client = await self._match_client_by_name(str(client_name) if client_name else None)
        if client is None:
            raise ValidationException("Client name could not be matched")
        global_data["client_name"] = client.client_name
        for employee_record in employee_records:
            employee_record.pop("client_match_failed", None)
            employee_record["extracted_client_name"] = (
                employee_record.get("extracted_client_name") or client_name
            )
        department_name = (
            payload.department_name
            or target_record.get("department")
            or global_data.get("department")
            or global_data.get("department_name")
        )
        if not department_name:
            raise ValidationException("Department name is required to process this employee")

        departments = await DepartmentRepository(self._db_session).get_by_client(
            client.client_id
        )
        department = await _fuzzy_match_department(str(department_name), departments)
        if department is None:
            raise ValidationException("Department name could not be matched")
        target_record["department"] = department.department_name
        target_record.pop("client_match_failed", None)
        target_record.pop("department_match_failed", None)

        candidates = await _get_candidate_employees(self._db_session, client)
        matched_record = _match_employees([target_record], candidates)[0]
        if not matched_record.get("emp_id"):
            raise ValidationException("Employee name could not be matched")
        target_record.update(matched_record)

        corrected_payload["global_data"] = global_data
        corrected_payload["employee_records"] = employee_records
        week_ending = _week_ending_from_payload(corrected_payload, timesheet.week_ending)

        failures: list[ValidationFailure] = []
        failures.extend(_validate_employee_record(target_record))
        if failures:
            employee_name = target_record.get("employee_name") or payload.employee_name
            reasons = [
                _exception_reason(exc_type, employee_name, record)
                for exc_type, _, record in failures
            ]
            raise ValidationException("; ".join(dict.fromkeys(reasons)))

        updated_timesheet = await self._timesheet_repository.update_timesheet(
            email_id=timesheet.email_id,
            client_name=client.client_name,
            week_ending=week_ending,
            payload=corrected_payload,
            status=TimesheetStatus.UNDER_REVIEW,
        )
        if updated_timesheet is None:
            raise ResourceNotFound("Timesheet not found for correction")
        await self._clear_week_ending_exceptions_for_timesheet(
            updated_timesheet.timesheet_id,
            week_ending,
        )
        await self._clear_client_exceptions_for_timesheet(
            updated_timesheet.timesheet_id,
        )

        rule = None
        if target_record.get("emp_id") and target_record.get("assignment_id"):
            rule = await _get_rule_for_assignment(
                self._db_session,
                target_record.get("assignment_id"),
            )
        payable_hours = _payable_weekly_hours(target_record, rule)
        reg_hours, ot_hours, dt_hours = _split_hours(payable_hours, rule)

        timecard.emp_id = _uuid_or_none(target_record.get("emp_id"))
        timecard.assignment_id = _uuid_or_none(target_record.get("assignment_id"))
        timecard.rule_id = rule.rule_id if rule is not None else None
        timecard.week_ending = week_ending
        timecard.employee_name = target_record.get("employee_name") or payload.employee_name
        timecard.reg_hours = reg_hours
        timecard.ot_hours = ot_hours
        timecard.dt_hours = dt_hours
        timecard.review_comment = payload.review_comment
        if payload.reviewed_by is not None:
            timecard.reviewed_by = payload.reviewed_by
        timecard.status = TimecardStatus.NO_EXCEPTION
        timecard.severity = TimecardSeverity.NONE

        await self._exception_repository.resolve_exceptions(timecard.exceptions)
        await self._db_session.flush()
        refreshed = await self._timecard_repository.get_by_id(timecard.timecard_id)
        if refreshed is None:
            raise ResourceNotFound("Timecard not found after correction")
        return refreshed

    async def _apply_matching_correction_payload(
        self,
        timecard: Timecard,
        payload: TimecardUpdate,
    ) -> Timesheet:
        timesheet = await self._timesheet_repository.get_by_id(
            timesheet_id=timecard.timesheet_id
        )
        if timesheet is None:
            raise ResourceNotFound("Timesheet not found for correction")

        correction_types = self._matching_exception_types(timecard)
        if ExceptionType.MISSING_CLIENT.value in correction_types and not payload.client_name:
            raise ValidationException("Client name is required to process matching")
        if (
            ExceptionType.MISSING_WEEK_ENDING.value in correction_types
            and payload.week_ending is None
        ):
            raise ValidationException("Week ending is required to process matching")
        if (
            ExceptionType.MISSING_DEPARTMENT.value in correction_types
            and not payload.department_name
        ):
            raise ValidationException("Department name is required to process matching")
        if (
            ExceptionType.MISSING_EMPLOYEE_ID.value in correction_types
            and not payload.employee_name
        ):
            raise ValidationException("Employee name is required to process matching")

        corrected_payload = self._with_corrected_matching_payload(
            timesheet.payload,
            original_employee_name=timecard.employee_name,
            employee_name=payload.employee_name,
            client_name=payload.client_name,
            department_name=payload.department_name,
            week_ending=payload.week_ending,
        )
        updated_timesheet = await self._timesheet_repository.update_timesheet(
            email_id=timesheet.email_id,
            client_name=payload.client_name,
            week_ending=payload.week_ending,
            payload=corrected_payload,
            status=TimesheetStatus.UNDER_REVIEW,
        )
        if updated_timesheet is None:
            raise ResourceNotFound("Timesheet not found for correction")
        return updated_timesheet

    @staticmethod
    def _matching_exception_types(timecard: Timecard) -> set[str]:
        return {
            str(exception.exception_type)
            for exception in timecard.exceptions
            if not exception.resolved
            and str(exception.exception_type) in MATCHING_CORRECTION_TYPES
        }

    @staticmethod
    def _normalize_name(value: str | None) -> str:
        return " ".join((value or "").strip().lower().split())

    @classmethod
    def _find_employee_record(
        cls,
        employee_records: list[dict[str, Any]],
        original_employee_name: str | None,
        employee_name: str | None,
    ) -> dict[str, Any] | None:
        lookup_names = {
            cls._normalize_name(name)
            for name in (original_employee_name, employee_name)
            if name
        }
        for record in employee_records:
            record_names = {
                cls._normalize_name(str(record.get("employee_name") or "")),
                cls._normalize_name(str(record.get("extracted_employee_name") or "")),
            }
            if lookup_names.intersection(record_names):
                return record
        if len(employee_records) == 1:
            return employee_records[0]
        return None

    @classmethod
    def _with_corrected_matching_payload(
        cls,
        raw_payload: Any,
        *,
        original_employee_name: str | None,
        employee_name: str | None,
        client_name: str | None,
        department_name: str | None,
        week_ending: date | None,
    ) -> dict[str, Any]:
        payload = dict(raw_payload or {}) if isinstance(raw_payload, dict) else {}
        global_data = dict(payload.get("global_data") or {})
        if client_name:
            global_data["client_name"] = client_name
        if week_ending is not None:
            global_data["week_ending"] = week_ending.isoformat()

        employee_records = [
            dict(record)
            for record in payload.get("employee_records") or []
            if isinstance(record, dict)
        ]
        target_record = cls._find_employee_record(
            employee_records,
            original_employee_name,
            employee_name,
        )
        if target_record is not None:
            if employee_name:
                target_record["employee_name"] = employee_name
            if department_name:
                target_record["department"] = department_name
                target_record.pop("department_match_failed", None)

        payload["global_data"] = global_data
        payload["employee_records"] = employee_records
        return payload

    async def _approve_with_payroll(self, timecard: Timecard) -> Timecard:
        if timecard.status == TimecardStatus.APPROVED and timecard.gross_pay is not None:
            return timecard

        if timecard.assignment_id is None:
            raise ValidationException("Timecard cannot be approved without an assignment")
        if timecard.rule_id is None:
            raise ValidationException("Timecard cannot be approved without a client rule")

        assignment = await self._timecard_repository.get_assignment(timecard.assignment_id)
        if assignment is None:
            raise ResourceNotFound("Assignment not found for timecard")
        if assignment.pay_rate <= 0:
            raise ValidationException("Assignment pay rate must be greater than zero")

        rule = await self._timecard_repository.get_client_rule(timecard.rule_id)
        if rule is None:
            raise ResourceNotFound("Client rule not found for timecard")

        reg_hours = timecard.reg_hours or Decimal("0")
        ot_hours = timecard.ot_hours or Decimal("0")
        dt_hours = timecard.dt_hours or Decimal("0")
        pay_rate = assignment.pay_rate

        regular_pay = self._money(reg_hours * pay_rate)
        ot_pay = self._money(ot_hours * pay_rate * rule.ot_multiplier)
        dt_pay = self._money(dt_hours * pay_rate * rule.dt_multiplier)
        gross_pay = self._money(regular_pay + ot_pay + dt_pay)

        return await self._timecard_repository.set_approved_payroll(
            timecard,
            pay_rate=self._money(pay_rate),
            regular_pay=regular_pay,
            ot_pay=ot_pay,
            dt_pay=dt_pay,
            gross_pay=gross_pay,
        )

    def _to_response(self, timecard: Timecard) -> TimecardResponse:
        return TimecardResponse.model_validate(timecard)

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(MONEY_QUANT)

    @staticmethod
    def _column_name(index: int) -> str:
        name = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            name = chr(65 + remainder) + name
        return name

    @classmethod
    def _build_xlsx(cls, rows: list[list[object]]) -> bytes:
        headers = [
            "Employee Name",
            "Regular Hours",
            "Overtime Hours",
            "Double Time Hours",
            "Pay Rate",
            "Regular Pay",
            "Overtime Pay",
            "Double Time Pay",
            "Gross Pay",
        ]
        sheet_rows: list[list[Any]] = [headers, *rows]
        xml_rows: list[str] = []

        for row_index, row in enumerate(sheet_rows, start=1):
            cells: list[str] = []
            for column_index, value in enumerate(row, start=1):
                cell_ref = f"{cls._column_name(column_index)}{row_index}"
                if isinstance(value, Decimal):
                    cells.append(f'<c r="{cell_ref}"><v>{value}</v></c>')
                elif isinstance(value, (int, float)):
                    cells.append(f'<c r="{cell_ref}"><v>{value}</v></c>')
                else:
                    text = escape(str(value))
                    cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{text}</t></is></c>')
            xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheetData>" + "".join(xml_rows) + "</sheetData></worksheet>"
        )

        output = BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as workbook:
            workbook.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                "</Types>",
            )
            workbook.writestr(
                "_rels/.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                "</Relationships>",
            )
            workbook.writestr(
                "xl/workbook.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Approved Timecards" sheetId="1" r:id="rId1"/></sheets>'
                "</workbook>",
            )
            workbook.writestr(
                "xl/_rels/workbook.xml.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                "</Relationships>",
            )
            workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        return output.getvalue()
