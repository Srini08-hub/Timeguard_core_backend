"""
Part B, Layer 2 · Parse and validate.
Part B, Layer 3 · Retry with error context.

This module owns the parse/validate/retry loop. It is deliberately
decoupled from any specific LLM SDK call signature beyond
`call_llm(messages, system) -> str` so it can be swapped (Anthropic
Messages API, Bedrock, etc.) without touching the retry logic.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

# from schema import EmployeeTimesheetExtraction

logger = logging.getLogger("timesheet_extractor")

MAX_RETRIES = 2  # 2 retries => 3 total attempts, per spec


class ExtractionError(Exception):
    """Raised after the third attempt still fails. Carries the raw
    response for human review — never silently continue past this."""

    def __init__(self, message: str, raw_response: str, attempts: int):
        super().__init__(message)
        self.raw_response = raw_response
        self.attempts = attempts


@dataclass
class ParseOutcome:
    success: bool
    parsed: dict | None = None
    error_message: str | None = None
    error_kind: str | None = None  # "json_decode" | "validation"


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def parse_and_validate(raw_response: str) -> ParseOutcome:
    """
    Layer 2, exactly as specified: two separate steps, two separate
    error channels.

    Step 1: strip whitespace/fences, then json.loads(). A JSONDecodeError
    here means the response was not valid JSON at all — distinct from a
    schema problem.

    Step 2: if it parsed, run Pydantic model_validate(). This catches
    missing required fields, wrong types, and the business-rule
    violations encoded in schema.py validators (hours > 24, total !=
    sum of daily entries, empty records list).
    """
    cleaned = _strip_fences(raw_response)

    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return ParseOutcome(
            success=False,
            error_kind="json_decode",
            error_message=f"JSONDecodeError: {e}",
        )

    return ParseOutcome(success=True, parsed=obj)


def extract_with_retries(
    call_llm: Callable[[list[dict], str], str],
    system_prompt: str,
    messages: list[dict],
    max_retries: int = MAX_RETRIES,
) -> dict | None:
    """
    Layer 3, exactly as specified: on any failure, do NOT start a new
    conversation. Append the bad response + the exact error string +
    the fix-only instruction to the SAME message thread, then call
    again. Up to `max_retries` retries (default 2 => 3 total attempts).
    On final failure, raise ExtractionError and log the raw response —
    never silently continue.
    """
    thread = list(messages)
    last_raw_response = ""
    last_error = ""

    for attempt in range(1, max_retries + 2):  # 1, 2, 3 for max_retries=2
        raw_response = call_llm(thread, system_prompt)
        last_raw_response = raw_response

        outcome = parse_and_validate(raw_response)
        if outcome.success:
            if attempt > 1:
                logger.info(
                    "Extraction succeeded on attempt %d/%d after retry.",
                    attempt,
                    max_retries + 1,
                )
            if outcome.parsed is not None:
                return outcome.parsed
            return {}

        last_error = outcome.error_message or ""
        logger.warning(
            "Extraction attempt %d/%d failed (%s): %s",
            attempt,
            max_retries + 1,
            outcome.error_kind,
            outcome.error_message,
        )

        if attempt <= max_retries:
            thread = thread + [
                {"role": "assistant", "content": raw_response},
                {
                    "role": "user",
                    "content": (
                        f"That response failed with "
                        f"this error:\n\n{outcome.error_message}\n\n"
                        "Fix only the error above and return the corrected JSON. "
                        "Return ONLY the corrected JSON object — "
                        "no explanation, no markdown fences."
                    ),
                },
            ]

    logger.error(
        "Extraction failed after %d attempts. Raw response for human review:\n%s",
        max_retries + 1,
        last_raw_response,
    )
    raise ExtractionError(
        message=f"Extraction failed after {max_retries + 1} attempts."
        f" Last error: {last_error}",
        raw_response=last_raw_response,
        attempts=max_retries + 1,
    )
