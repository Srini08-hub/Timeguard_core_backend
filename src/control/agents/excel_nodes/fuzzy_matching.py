from rapidfuzz import fuzz

from src.control.agents.state import ExcelClassifierState

ANCHOR_KEYWORDS = [
    "timesheet",
    "time sheet",
    "hours worked",
    "total hours",
    "week ending",
    "overtime",
    "ot",
    "dt",
    "holiday",
    "pay period",
    "time in",
    "time out",
    "billable hours",
    "clock in",
    "clock out",
    "attendance",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "employee",
    "department",
    "project code",
    "approved",
    "supervisor",
]
FUZZY_THRESHOLD = 88
# WINDOW_SIZE     = 60


def find_keyword_position(
    keyword: str, text: str, threshold: float
) -> tuple[bool, float, int]:
    kw = keyword.lower()
    txt = text.lower()

    idx = txt.find(kw)
    if idx != -1:
        return True, 100.0, idx

    win = len(kw) + 10
    best_score: float = 0.0
    best_pos = -1
    for i in range(0, max(1, len(txt) - win + 1), 5):
        chunk = txt[i : i + win]
        # score = fuzz.partial_ratio(kw, chunk)
        score = fuzz.token_set_ratio(kw, chunk)
        if score > best_score:
            best_score, best_pos = float(score), i

    if best_score >= threshold:
        return True, float(best_score), best_pos

    return False, 0.0, -1


def fuzzy_match_anchors(state: ExcelClassifierState) -> ExcelClassifierState:
    sheet = state.get("current_sheet")
    text = sheet.get("combined", "") if sheet else ""
    hits = []

    for kw in ANCHOR_KEYWORDS:
        found, score, pos = find_keyword_position(kw, text, FUZZY_THRESHOLD)
        if found:
            hits.append({"keyword": kw, "score": score, "position": pos})
    hits = sorted(
        hits,
        key=lambda h: h["score"] if isinstance(h["score"], (int, float)) else 0.0,
        reverse=True,
    )[:3]

    return {
        **state,
        "anchor_hits": hits,
        "sheets_checked": state.get("sheets_checked", 0) + 1,
    }
