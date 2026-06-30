"""
Concrete call_llm implementation against Groq via langchain_groq.

This is the only place that talks to the network. Everything in
llm_client.py is provider-agnostic and just needs a callable matching
call_llm(messages, system) -> str.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from src.config.settings import settings

MODEL_NAME = "llama-3.3-70b-versatile"
# MODEL_NAME="qwen/qwen3-32b"
# MODEL_NAME = "openai/gpt-oss-120b"
LLM_PAYLOAD_LOG = Path("results") / "llm_payloads.jsonl"

_client = None
_payload_log_lock = threading.Lock()


def _get_client() -> Any:
    global _client
    if _client is None:
        api_key = settings.GROQ_API_KEY_1
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Export it before calling the "
                "Groq-backed extractor, "
                "e.g.: export GROQ_API_KEY=gsk_..."
            )
        base_client = ChatGroq(
            model_name=MODEL_NAME,
            api_key=api_key,
            temperature=0,
            max_tokens=4096,
        )
        _client = base_client.bind(response_format={"type": "json_object"})
    return _client


def _to_langchain_messages(messages: list[dict], system: str) -> list:
    """
    Convert provider-agnostic dict messages into LangChain messages, with
    the system prompt prepended as its own message.
    """
    lc_messages: list = [SystemMessage(content=system)]
    for m in messages:
        if m["role"] == "user":
            lc_messages.append(HumanMessage(content=m["content"]))
        elif m["role"] == "assistant":
            lc_messages.append(AIMessage(content=m["content"]))
        else:
            raise ValueError(f"Unexpected message role: {m['role']!r}")
    return lc_messages


def _write_llm_payload(messages: list[dict], system: str) -> None:
    """Append the exact outgoing LLM payload to one JSONL debug file."""
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "model": MODEL_NAME,
        "system": system,
        "messages": messages,
        "total_content_chars": len(system) + sum(len(m.get("content", "")) for m in messages),
    }

    LLM_PAYLOAD_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False)
    with _payload_log_lock:
        with LLM_PAYLOAD_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def call_groq(messages: list[dict], system: str) -> str:
    """
    Matches the call_llm(messages, system) -> str signature expected by
    llm_client.extract_with_retries.
    """
    _write_llm_payload(messages, system)
    client = _get_client()
    lc_messages = _to_langchain_messages(messages, system)
    response = client.invoke(lc_messages)
    content = response.content
    if isinstance(content, str):
        return content
    return str(content)
