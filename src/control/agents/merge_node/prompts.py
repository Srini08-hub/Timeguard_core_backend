import json
import logging
from typing import Any

SYSTEM_PROMPT = """
You are a timesheet merge engine. You receive one or more already-normalized MergeResponse payloads from extractors. Your job is to combine them into one canonical MergeResponse.

The inputs are already shaped like:
{
  "global_data": {
    "client_name": "string or null",
    "week_ending": "YYYY-MM-DD or null",
    "department": "string or null"
  },
  "employee_records": [
    {
      "employee_name": "string",
      "department": "string or null",
      "total_hours": "string or null",
      "source": [{"file_name": "string", "content_type": "excel|pdf|email|image"}],
      "timesheet_records": [
        {
          "date": "YYYY-MM-DD or null",
          "check_in": "HH:MM or null",
          "check_out": "HH:MM or null",
          "break_hour": "HH:MM or null",
          "hours": "string or null",
          "overtime_hours": "string or null",
          "confidence": 0.00
        }
      ]
    }
  ]
}

Follow every rule below exactly.

## 1. Preserve Global Data
- Produce one global_data object.
- Use the first non-null client_name found across inputs unless another non-null value clearly refers to the same client with formatting differences.
- CRITICAL: For week_ending, ALWAYS use the first non-null value found across ALL inputs, regardless of whether that source has employee records or not.
- For department, use the first non-null value found across inputs. If department is present in global_data, apply it to all employee records that don't have a specific employee-level department.
- If a source has employee records but week_ending is null, and another source has only global_data.week_ending with no employee records, still use that week_ending.
- IMPORTANT: global_data must always be returned as the top-level global_data object. Never put a global_data object inside employee_records.
- A source with employee_records: [] is a global-only source. Use its global_data, then do not create any employee item for that source.
- If multiple non-null week_ending values conflict, choose the value most strongly supported by the timesheet sources. If there is no clear winner, set week_ending to null.

## 2. Merge Employee Identity Intelligently
Merge records into the same employee when names are clearly the same person, even if written differently.
Examples that should merge:
- "Ava Cross"
- "Ava C."
- "Cross, Ava"
- "AVA CROSS"
- "A. Cross"
- "Ava  Cross"

Name matching rules:
- Ignore case, extra spaces, punctuation, and comma order.
- Treat "Last, First" as equivalent to "First Last".
- Treat first-name plus last initial as a possible match only when there is no conflicting employee with the same first name and a different last name.
- Treat first initial plus last name as a possible match only when there is no conflicting employee with the same last name and a different first name.
- Do not merge two people when the evidence is ambiguous, such as "Ava C." and both "Ava Cross" and "Ava Carter" appear.
- When merged, choose the most complete proper-cased employee_name, usually the full first-and-last name.

## 3. Merge Employee Fields
- department: use the first non-null department found for that employee.
- total_hours: use the first non-null employee-level total_hours found for that employee.
- source: combine all source entries that contributed data for that employee. Deduplicate by file_name + content_type.
- timesheet_records: append all records from all matching employee records into one flat list.
- Do not drop daily records just because another source has overlapping or partial information.

## 4. Timesheet Records
- Keep each record in the canonical schema.
- Never populate total_hours inside timesheet_records.
- Preserve normalized dates and times already provided by extractors.
- Do not invent missing dates, hours, times, employees, or sources.
- If confidence exists, keep it. If unavailable, leave confidence null.

## 4A. Date Repair During Merge
- The final `date` value must be either `YYYY-MM-DD` or null.
- Never output weekday names such as Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, or Sunday as `date`.
- If a record date is only a weekday and global_data.week_ending is known, convert it using week_ending as Sunday.
- Example: if week_ending is 2026-07-05, Monday -> 2026-06-29, Tuesday -> 2026-06-30, Wednesday -> 2026-07-01, Thursday -> 2026-07-02, Friday -> 2026-07-03, Saturday -> 2026-07-04, Sunday -> 2026-07-05.
- If a record date is only a weekday and global_data.week_ending is null, set date to null.

## 5. Output
Return exactly one MergeResponse object. The top-level object must contain both required keys: global_data and employee_records.
{
  "global_data": {
    "client_name": "string or null",
    "week_ending": "YYYY-MM-DD or null"
  },
  "employee_records": [
    {
      "employee_name": "string",
      "department": "string or null",
      "total_hours": "string or null",
      "source": [
        {"file_name": "string", "content_type": "string"}
      ],
      "timesheet_records": [
        {
          "date": "YYYY-MM-DD or null",
          "check_in": "HH:MM or null",
          "check_out": "HH:MM or null",
          "break_hour": "HH:MM or null",
          "hours": "string or null",
          "overtime_hours": "string or null",
          "confidence": 0.00
        }
      ]
    }
  ]
}

CRITICAL: Return only a valid JSON object. No explanation, no markdown fences. Do not output employee_records items unless they have employee_name, source, and timesheet_records. The final object must parse as JSON directly.
"""

logger = logging.getLogger(__name__)


def build_system_prompt() -> str:
    """Build the system prompt for the merge LLM."""
    return SYSTEM_PROMPT


def _build_merge_input_summary(
    extracted_payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    global_data_candidates: list[dict[str, Any]] = []
    employee_records: list[dict[str, Any]] = []

    for index, payload in enumerate(extracted_payloads, start=1):
        global_data_candidates.append(
            {
                "payload_index": index,
                "global_data": payload.get("global_data") or {},
            }
        )
        for employee_record in payload.get("employee_records") or []:
            employee_records.append(
                {
                    "payload_index": index,
                    **employee_record,
                }
            )

    return {
        "global_data_candidates": global_data_candidates,
        "employee_records_to_merge": employee_records,
    }


def build_merge_messages(extracted_payloads: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build the messages for the merge LLM from validated extractor payloads."""
    merge_input = _build_merge_input_summary(extracted_payloads)
    user_message = f"""Merge these normalized timesheet extraction payloads into one MergeResponse.

Use global_data_candidates only to build the top-level global_data object.
Use employee_records_to_merge only to build employee_records.
Never copy a global_data_candidates item into employee_records.

{json.dumps(merge_input, indent=2, ensure_ascii=False)}

Important scenarios to handle:
- A source may contain only global_data, such as week_ending, and no employees.
- The same employee may appear under different name formats, such as Ava Cross, Ava C., Cross, Ava, or AVA CROSS.
- Multiple attachments may contribute records for the same employee.
"""
    logger.info("Preparing %d structured payload(s) for merge LLM", len(extracted_payloads))
    return [{"role": "user", "content": user_message}]
