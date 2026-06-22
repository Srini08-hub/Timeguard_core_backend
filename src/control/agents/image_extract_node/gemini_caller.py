"""Gemini vision LLM caller for image timesheet extraction."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config.settings import settings

MODEL_NAME = "gemini-2.5-flash"

_client: ChatGoogleGenerativeAI | None = None


def _get_client() -> ChatGoogleGenerativeAI:
    global _client
    if _client is None:
        _client = ChatGoogleGenerativeAI(
            model=MODEL_NAME,
            temperature=0,
            api_key=settings.GOOGLE_API_KEY,
        )
    return _client


def _to_langchain_messages(messages: list[dict], system: str) -> list:
    lc_messages: list = [SystemMessage(content=system)]
    for message in messages:
        role = message["role"]
        content = message["content"]
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            if not isinstance(content, str):
                raise ValueError("Assistant message content must be a string")
            lc_messages.append(AIMessage(content=content))
        else:
            raise ValueError(f"Unexpected message role: {role!r}")
    return lc_messages


def call_gemini_vision(messages: list[dict], system: str) -> str:
    """Matches call_llm(messages, system) -> str for extract_with_retries."""
    client = _get_client()
    lc_messages = _to_langchain_messages(messages, system)
    response = client.invoke(lc_messages)
    content = response.content
    if not isinstance(content, str):
        raise ValueError("Expected Gemini response content to be a string")
    return content
