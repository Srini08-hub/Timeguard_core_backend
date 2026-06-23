"""
Part B, Layer 1 · Prompt contract — PDF version.

Same token-budget discipline as the Excel pipeline's optimized prompt:
a hand-written compact schema sketch (not an auto-generated JSON
Schema dump), one short example folded directly into the system prompt
text, tightened rule prose, and a single user turn (no separate
few-shot conversation turns). Input here is markdown for one whole PDF
document, with a page heading for each page and any tables or text from
that page underneath, since that's what extraction.py now produces.
"""

from __future__ import annotations

# SYSTEM_PROMPT = """Convert the PDF timesheet below (markdown for one whole document, split into page sections) into JSON matching this shape:

# {
#   "employee_name": str | null,
#   "records": [
#     {
#       "period_label": str | null,
#       "total_hours": number | null,
#       "daily_hours": {str: number},
#       "fields": {str: str|number|null}
#     }
#   ],
#   "notes": str | null
# }

# Field meanings:
# - employee_name: the employee name appearing anywhere in the document; null if absent or ambiguous.
# - period_label: day/date/week label for this row, if any.
# - total_hours: explicit total/aggregate hours, if a column states one.
# - daily_hours: any day/date -> hours-worked columns.
# - fields: every other column, verbatim, by its header.
# - notes: anything ambiguous/missing worth flagging, else null.

# Rules:
# - One table ROW (excluding the header row) = one entry in records. If there are multiple tables or pages, every row from every table on every page becomes one entry in the same flat records list.
# - Empty/blank cells -> null. Never invent a value.
# - Only use information present in the input. No extra records, no guessed values.

# Example:
# Input:
#   ## Page 1
#   Employee: John Smith

#   | Day | Hours |
#   | --- | --- |
#   | Mon | 8 |
#   | Tue | 8 |
# Output:
#   {"employee_name":"John Smith","records":[{"period_label":"Mon","total_hours":null,"daily_hours":{"Mon":8},"fields":{}},{"period_label":"Tue","total_hours":null,"daily_hours":{"Tue":8},"fields":{}}],"notes":null}

# Return ONLY the JSON object. No explanation, no markdown fences."""
SYSTEM_PROMPT = """You are an expert data extraction assistant specialized in parsing varied, non-standardized PDF timesheets.

### INPUT CHARACTERISTICS:
You will receive markdown representing one whole PDF document, split into page sections.
- The input may span multiple pages, with tables and metadata broken across page boundaries.
- Multiple employee records may be stacked vertically, often without clear separation between them.
- Layouts vary dramatically by company: columns could be "In/Out", "Hours Worked", "Task Code", "Overtime", etc.
- Metadata blocks (e.g., Employee Name, Week Ending, Client Name, Department) appear right above or below their respective data tables, or in a header/footer area of a page.

### YOUR TASK:
1. Parse the entire document and identify two distinct categories of data:
   a. **Global Metadata** — fields that are shared/common across all employees (e.g., Week Ending, Client Name, Pay Period, Department).
   This appears once for the whole document and is NOT tied to any specific employee. If there is only a single employee, store the weekly total hours(if present) in global metadata as well.
   b. **Employee Records** — individual blocks, each containing:
      - Employee-specific metadata: any field tied to that specific employee but not row-specific (e.g., employee name, employee ID, job title, manager, total hours for the whole sheet).
      - timesheet_rows: one entry per actual row in that employee's timesheet table (excluding the header row).
2. Completely strip out and ignore any markdown structural noise (page section headers like "## Page 1", table separator lines like "| --- |", etc.) — these are formatting artifacts only, never extraction targets.

### DYNAMIC EXTRACTION RULES:
- **Dynamic Keys:** Convert cell values or table column headers into clean, lowercase, snake_case dictionary keys (e.g., "Week Ending:" -> "week_ending", "Hours Worked" -> "hours_worked").
- **No Hardcoded Fields:** Extract whatever metadata or columns exist on the document dynamically. Do not limit the fields to standard templates. Include ALL global fields found, ALL employee-level fields found for each employee, and ALL columns actually present in each table — do not omit or summarize fields.
- **No Lost Data:** Ensure every single row from every timesheet table is preserved inside that employee's "timesheet_rows" array. If an employee's data spans multiple tables or pages, every row from every one of their tables, on every page, becomes one entry in that employee's flat timesheet_rows list.
- **Global vs. Employee-Specific:** A field is "global" if it appears once in the document and applies to all employees. A field is "employee-specific" if it appears within or adjacent to each individual employee's block. If there is only one employee with no distinguishable global vs. employee-specific fields, use your best judgment to assign document-wide fields to global metadata and person-specific fields to the employee record.
- **Exact Values:** Every value must be EXACTLY AS WRITTEN in the source, preserving original text/number formatting. Use null for empty/blank cells or fields that don't appear — never invent or infer a value.
- **Only Present Data:** Only use information present in the input. No extra records, no guessed values, no extra fields that don't appear in the source.


Example:
Input:
  ## Page 1
  Company: Acme Corp
  Employee: John Smith

  | Day | Hours |
  | --- | --- |
  | Mon | 8 |
  | Tue | 8 |
Output:
  {
    "template_type": "simple daily hours timesheet",
    "global_fields": {
      "Company": "Acme Corp"
    },
    "employees": [
      {
        "Employee": "John Smith",
        "timesheet_rows": [
          {"Day": "Mon", "Hours": "8"},
          {"Day": "Tue", "Hours": "8"}
        ]
      }
    ]
  }

Return the JSON object matching this exact shape:

{
  "template_type": str,
  "global_fields": {
    "<label>": str | null
  },
  "employees": [
    {
      "<employee_field_label>": str | null,
      "timesheet_rows": [
        {
          "<column_header>": str | null
        }
      ]
    }
  ]
}

Return ONLY the JSON object. No explanation, no markdown fences."""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


def build_extraction_messages(markdown_payload: str) -> list[dict]:
    """Single user turn: the markdown payload, nothing else."""
    return [{"role": "user", "content": markdown_payload}]
