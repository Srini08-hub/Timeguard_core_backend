from datetime import date
from decimal import Decimal
from io import BytesIO
from uuid import UUID
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from src.core.exceptions.custom_exception import ResourceNotFound, ValidationException
from src.data.models.timecard import Timecard, TimecardStatus
from src.data.repositories.exception_repository import ExceptionRepository
from src.data.repositories.timecard_repository import TimecardRepository
from src.schemas.timecard_schema import TimecardResponse, TimecardUpdate

MONEY_QUANT = Decimal("0.01")


class TimecardService:
    def __init__(
        self,
        timecard_repository: TimecardRepository,
        exception_repository: ExceptionRepository,
    ) -> None:
        self._timecard_repository = timecard_repository
        self._exception_repository = exception_repository

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
        updated = await self._timecard_repository.resolve_with_update(
            timecard,
            employee_name=payload.employee_name,
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
        sheet_rows = [headers, *rows]
        xml_rows: list[str] = []

        for row_index, row in enumerate(sheet_rows, start=1):
            cells: list[str] = []
            for column_index, value in enumerate(row, start=1):  # type: ignore[var-annotated, arg-type]
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
