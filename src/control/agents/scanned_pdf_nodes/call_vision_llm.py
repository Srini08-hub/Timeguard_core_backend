from enum import StrEnum

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from src.config.settings import settings
from src.control.agents.state import ScannedPDFClassifierState


class ScannedPDFClassification(StrEnum):
    TIMESHEET = "TIMESHEET"
    NOT_A_TIMESHEET = "NOT_A_TIMESHEET"


class ScannedPDFClassificationResponse(BaseModel):
    classification: ScannedPDFClassification = Field(
        description="Whether the scanned PDF page is a timesheet."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Model confidence from 0.0 to 1.0.",
    )
    reason: str = Field(
        min_length=1,
        description="Short rationale based only on visible page evidence.",
    )


def call_vision_llm(
    state: ScannedPDFClassifierState,
) -> ScannedPDFClassifierState:
    current_page = state.get("current_page")
    if current_page is None:
        return {**state, "scanned_pdf_classification": "NOT_A_TIMESHEET"}

    prompt = """Classify this scanned PDF page as a timesheet or not.

A timesheet usually contains visible evidence such as employee names or IDs,
dates or pay periods, days of the week, clock in/out times, hours worked,
total hours, client/project rows, approvals, or signatures.

Base the answer only on the page image. If the page is unreadable or lacks
enough timesheet evidence, classify it as not a timesheet with lower confidence."""

    llm = ChatGoogleGenerativeAI(
        # model="gemini-2.5-flash",
        model="gemini-2.5-flash-lite",
        temperature=0,
        api_key=settings.GOOGLE_API_KEY,
    )
    structured_llm = llm.with_structured_output(ScannedPDFClassificationResponse)
    response = structured_llm.invoke(
        [
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                f"data:{current_page['image_media_type']};base64,"
                                f"{current_page['image_base64']}"
                            )
                        },
                    },
                ]
            )
        ]
    )

    if not isinstance(response, ScannedPDFClassificationResponse):
        raise ValueError("Invalid scanned PDF classification response type")

    # final_status = state.get("final_status")
    # if response.classification == ScannedPDFClassification.TIMESHEET:
    #     final_status = response.classification.value
    # elif not state.get("page_queue"):
    #     final_status = response.classification.value

    next_state: ScannedPDFClassifierState = {
        **state,
        "scanned_pdf_classification": response.classification.value,
        # "confidence": response.confidence,
        # "reason": response.reason,
    }
    # if final_status is not None:
    #     next_state["final_status"] = final_status

    return next_state
