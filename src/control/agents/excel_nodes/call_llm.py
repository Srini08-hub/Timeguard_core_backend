from enum import StrEnum

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from src.config.settings import settings
from src.control.agents.state import ExcelClassifierState


class Excelclassifier(StrEnum):
    TIMESHEET = "TIMESHEET"
    NOT_A_TIMESHEET = "NOT_A_TIMESHEET"


class ExcelClassificationResponse(BaseModel):
    classification: Excelclassifier = Field(
        description="Whether the page belongs to a timesheet"
    )
    reason: str = Field(description="Short explanation for the classification")


def call_llm(state: ExcelClassifierState) -> ExcelClassifierState:
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

    structured_llm = llm.with_structured_output(ExcelClassificationResponse)
    response = structured_llm.invoke([HumanMessage(content=prompt)])

    if not isinstance(response, ExcelClassificationResponse):
        raise ValueError("Invalid LLM response type")

    return {
        **state,
        "excel_classification": response.classification.value,
        "reason": response.reason,
    }
