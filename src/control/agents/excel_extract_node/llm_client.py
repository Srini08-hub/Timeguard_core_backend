"""
Part B, Layer 2 - Parse JSON.
Part B, Layer 3 - Retry malformed JSON with error context.

This module owns the parse/retry loop. It is deliberately decoupled from
any specific LLM SDK call signature beyond call_llm(messages, system) -> str
so it can be swapped without touching the retry logic.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("timesheet_extractor")

MAX_RETRIES = 2  # 2 retries => 3 total attempts


class ExtractionError(Exception):
    """Raised after all attempts fail. Carries the raw response for review."""

    def __init__(self, message: str, raw_response: str, attempts: int):
        super().__init__(message)
        self.raw_response = raw_response
        self.attempts = attempts


@dataclass
class ParseOutcome:
    success: bool
    parsed: dict[str, Any] | None = None
    error_message: str | None = None
    error_kind: str | None = None  # "json_decode" | "not_object"


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


def parse_llm_json(raw_response: str) -> ParseOutcome:
    """
    Strip whitespace/fences, then json.loads().

    Pydantic validation is intentionally skipped for now to avoid
    validation-driven retries that resend large JSON payloads and burn
    through the model context window. The only enforced contract here is
    syntactically valid top-level JSON object output.
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

    if not isinstance(obj, dict):
        return ParseOutcome(
            success=False,
            error_kind="not_object",
            error_message="Expected the LLM response to be a top-level JSON object.",
        )

    return ParseOutcome(success=True, parsed=obj)


# Backwards-compatible name for callers/tests that still import it.
parse_and_validate = parse_llm_json


def extract_with_retries(
    call_llm: Callable[[list[dict], str], str],
    system_prompt: str,
    messages: list[dict],
    max_retries: int = MAX_RETRIES,
) -> dict[str, Any]:
    """
    On malformed JSON, retry in the same conversation with the exact parse
    error. Successful responses are returned as plain dictionaries.
    """
    thread = list(messages)
    last_raw_response = ""
    last_error = ""

    for attempt in range(1, max_retries + 2):
        raw_response = call_llm(thread, system_prompt)
        last_raw_response = raw_response

        outcome = parse_llm_json(raw_response)
        if outcome.success:
            if attempt > 1:
                logger.info(
                    "Extraction succeeded on attempt %d/%d after retry.",
                    attempt,
                    max_retries + 1,
                )
            if outcome.parsed is None:
                raise RuntimeError("parse_llm_json succeeded without parsed output")
            return outcome.parsed

        last_error = outcome.error_message or "Unknown parse error"
        logger.warning(
            "Extraction attempt %d/%d failed (%s): %s",
            attempt,
            max_retries + 1,
            outcome.error_kind,
            last_error,
        )

        if attempt <= max_retries:
            thread = thread + [
                {"role": "assistant", "content": raw_response},
                {
                    "role": "user",
                    "content": (
                        f"That response failed with this error:\n\n{last_error}\n\n"
                        "Fix only the error above and return the corrected JSON. "
                        "Return ONLY the corrected JSON object -"
                        " no explanation, no markdown fences."
                    ),
                },
            ]

    logger.error(
        "Extraction failed after %d attempts. Raw response for human review:\n%s",
        max_retries + 1,
        last_raw_response,
    )
    raise ExtractionError(
        message=f"Extraction failed after {max_retries + 1} attempts. "
        f"Last error: {last_error}",
        raw_response=last_raw_response,
        attempts=max_retries + 1,
    )
