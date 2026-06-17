from enum import StrEnum

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from src.config.settings import settings
from src.control.agents.state import PDFClassifierState


class PDFClassification(StrEnum):
    TIMESHEET = "TIMESHEET"
    NOT_A_TIMESHEET = "NOT_A_TIMESHEET"


class PDFClassificationResponse(BaseModel):
    classification: PDFClassification = Field(
        description="Whether the page belongs to a timesheet"
    )
    reason: str = Field(description="Short explanation for the classification")


def call_llm(state: PDFClassifierState) -> PDFClassifierState:
    prompt = f"""You are a document classifier.

Based ONLY on the extracted snippets below, decide if this page is from a TIMESHEET.

A timesheet has: employee name/ID, dates or days of week, hours worked/in/out,
total hours, pay period, or approval signatures.

SNIPPETS:
{state["context_snippet"]}

Reply in exactly this format:
CLASSIFICATION: [TIMESHEET / NOT_A_TIMESHEET]

REASON: [one sentence]
"""

    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile",
        temperature=0,
        api_key=settings.GROQ_API_KEY,
    )
    structured_llm = llm.with_structured_output(PDFClassificationResponse)
    response = structured_llm.invoke([HumanMessage(content=prompt)])

    if not isinstance(response, PDFClassificationResponse):
        raise ValueError("Invalid LLM response type")

    # raw = response.content.strip()

    # parsed = {
    #     "pdf_classification": "UNCERTAIN",
    #     "pdf_confidence": "LOW",
    #     "pdf_reason": "",
    # }

    # for line in raw.splitlines():
    #     if line.startswith("CLASSIFICATION:"):
    #         parsed["pdf_classification"] = line.split(":", 1)[1].strip()

    #     elif line.startswith("CONFIDENCE:"):
    #         parsed["pdf_confidence"] = line.split(":", 1)[1].strip()

    #     elif line.startswith("REASON:"):
    #         parsed["pdf_reason"] = line.split(":", 1)[1].strip()

    # parsed["status"] = (
    #     "classified"
    #     if parsed["pdf_classification"] in ("TIMESHEET", "NOT_A_TIMESHEET")
    #     else "uncertain"
    # )

    return {
        **state,
        "pdf_classification": response.classification.value,
        "pdf_reason": response.reason,
    }
