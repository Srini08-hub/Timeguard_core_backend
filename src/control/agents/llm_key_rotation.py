"""Utilities for retrying Groq LLM calls across configured API keys."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel

from src.config.settings import settings

logger = logging.getLogger(__name__)

GROQ_API_KEY_NAMES = tuple(f"GROQ_API_KEY_{index}" for index in range(1, 7))


def _iter_exception_chain(exc: BaseException) -> Iterator[BaseException]:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def is_rate_limit_error(exc: BaseException) -> bool:
    """Return True for common Groq/LangChain rate-limit wrappers."""
    for chained_exc in _iter_exception_chain(exc):
        class_name = chained_exc.__class__.__name__.lower()
        if "ratelimit" in class_name or "rate_limit" in class_name:
            return True

        status_code = getattr(chained_exc, "status_code", None)
        if status_code == 429:
            return True

        response = getattr(chained_exc, "response", None)
        if getattr(response, "status_code", None) == 429:
            return True

        error_code = getattr(chained_exc, "code", None)
        if isinstance(error_code, str) and error_code.lower() in {
            "rate_limit_exceeded",
            "too_many_requests",
        }:
            return True

        message = str(chained_exc).lower()
        if (
            "rate limit" in message
            or "rate_limit" in message
            or "too many requests" in message
            or "429" in message
        ):
            return True

    return False


def _configured_groq_api_keys(preferred_key_name: str | None = None) -> list[tuple[str, str]]:
    key_names = list(GROQ_API_KEY_NAMES)
    if preferred_key_name in key_names:
        key_names.remove(preferred_key_name)
        key_names.insert(0, preferred_key_name)

    keys: list[tuple[str, str]] = []
    seen_values: set[str] = set()
    for key_name in key_names:
        key_value = getattr(settings, key_name, None)
        if not key_value or key_value in seen_values:
            continue
        keys.append((key_name, key_value))
        seen_values.add(key_value)

    return keys


def invoke_groq_structured_with_key_rotation[T: BaseModel](
    *,
    model_name: str,
    output_schema: type[T],
    messages: Sequence[BaseMessage],
    preferred_key_name: str | None = None,
    temperature: float = 0,
    operation_name: str = "Groq LLM call",
) -> T | Any:
    """Invoke a structured Groq call, rotating API keys only on rate-limit errors."""
    api_keys = _configured_groq_api_keys(preferred_key_name)
    if not api_keys:
        raise RuntimeError("No Groq API keys are configured.")

    last_rate_limit_error: BaseException | None = None
    for key_index, (key_name, api_key) in enumerate(api_keys, start=1):
        llm = ChatGroq(
            model_name=model_name,
            api_key=api_key,
            temperature=temperature,
        )
        structured_llm = llm.with_structured_output(output_schema)

        try:
            if key_index > 1:
                logger.info(
                    "%s retrying with %s after rate limit",
                    operation_name,
                    key_name,
                )
            return structured_llm.invoke(messages)
        except Exception as exc:
            if not is_rate_limit_error(exc):
                raise

            last_rate_limit_error = exc
            logger.warning(
                "%s hit rate limit with %s (%d/%d): %s",
                operation_name,
                key_name,
                key_index,
                len(api_keys),
                exc,
            )

    assert last_rate_limit_error is not None
    raise last_rate_limit_error
