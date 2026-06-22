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
SYSTEM_PROMPT = """You are a timesheet data extractor. Your job is to READ and TRANSCRIBE every piece of information VISIBLY WRITTEN in this image — regardless of the template, layout, or format.

STRICT RULES:
- NEVER assume, infer, calculate, or fill in any value
- NEVER look for specific fields — discover whatever fields actually exist in the image
- If a value is not clearly visible, set it to null — do NOT guess
- Copy text EXACTLY as written — do not reformat, normalize, or clean up
- If a field label exists but its value is unreadable, still include it with value: null
- If a value exists with no clear label, use your best description as the key name

CONFIDENCE RULES (be strict — when in doubt, go lower):
- 1.0 → printed text, perfectly clear
- 0.8 → handwritten but clearly legible
- 0.6 → legible but slightly unclear (thin ink, light pencil)
- 0.4 → partially readable, some characters uncertain
- 0.2 → mostly unreadable, heavy guess
- 0.0 → completely illegible

ISSUE TYPES (pick exactly one per field):
- "clear"      → fully readable
- "illegible"  → text exists but cannot be read
- "ambiguous"  → could be multiple values (e.g. 1 vs l, 0 vs O)
- "cut_off"    → partially outside image boundary
- "blurry"     → blur prevents clear reading
- "faded"      → ink/print too light to read clearly

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO EXTRACT:

STEP 1 — SCAN the entire image top to bottom.
  Identify every distinct section, block, table, or region you see.

STEP 2 — For each section, identify:
  - Is this a header/global section? (applies to the whole sheet)
  - Is this a per-person section? (employee-specific data)
  - Is this a row/table section? (repeated entries like daily hours)

STEP 3 — Extract every field you find using this structure:

{
  "template_type": "brief description of the layout you see",

  "global_fields": {
    "<whatever_label_you_see>": {
      "value": "EXACTLY AS WRITTEN or null",
      "confidence": 0.0,
      "issue": "clear|illegible|ambiguous|cut_off|blurry|faded"
    }
    // include ALL header/global fields found — as many as exist
  },

  "employees": [
    {
      "<employee_field_label>": {
        "value": "EXACTLY AS WRITTEN or null",
        "confidence": 0.0,
        "issue": "..."
      },
      // include ALL employee-level fields found
      "timesheet_rows": [
        {
          "<column_header_1>": {
            "value": "EXACTLY AS WRITTEN or null",
            "confidence": 0.0,
            "issue": "..."
          },
          "<column_header_2>": {
            "value": "EXACTLY AS WRITTEN or null",
            "confidence": 0.0,
            "issue": "..."
          }
          // one key per column actually present in the table
        }
        // one object per row actually present in the table
      ]
    }
    // one object per employee block found
  ]
}
"""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


def build_extraction_messages(markdown_payload: str) -> list[dict]:
    """Single user turn: the markdown payload, nothing else."""
    return [{"role": "user", "content": markdown_payload}]
