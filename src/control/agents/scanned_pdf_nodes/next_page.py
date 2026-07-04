import base64

import fitz

from src.control.agents.state import TimeguardState

RENDER_ZOOM = 2


def next_page(state: TimeguardState) -> TimeguardState:
    queue = state.get("scanned_pdf_page_queue", [])

    # if not queue:
    #     final_status = state.get("scanned_pdf_classification") or "NOT_A_TIMESHEET"
    #     return {
    #         **state,
    #         "scanned_pdf_current_page": None,
    #         "scanned_pdf_classification": final_status,
    #     }

    page_index = queue[0]
    doc = fitz.open(state["scanned_pdf_file_path"])
    try:
        page = doc.load_page(page_index)
        matrix = fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        image_base64 = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
    finally:
        doc.close()

    return {
        **state,
        "scanned_pdf_current_page": {
            # "page_num": page_index + 1,
            "image_base64": image_base64,
            "image_media_type": "image/png",
        },
        "scanned_pdf_page_queue": queue[1:],
        # "scanned_pdf_pages_checked": state.get("scanned_pdf_pages_checked", 0) + 1,
        "scanned_pdf_classification": state.get(
            "scanned_pdf_classification", "NOT_A_TIMESHEET"
        ),
        # "scanned_pdf_confidence": 0.0,
    }
