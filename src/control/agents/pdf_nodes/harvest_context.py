from src.control.agents.state import TimeguardState


def harvest_context(state: TimeguardState) -> TimeguardState:
    page = state.get("pdf_current_page")
    if not page:
        return state
    text = page.get("combined", "")
    hits = state.get("pdf_anchor_hits", [])
    chunks = []

    for hit in hits:
        pos = hit["position"]
        # chars before and after the keyword position
        start = max(0, pos - 300)
        end = min(len(text), pos + 300)
        snip = text[start:end].strip()
        chunks.append(f"[keyword: '{hit['keyword']}' | score: {hit['score']:.0f}%]\n{snip}")

    # for t_idx, table in enumerate(page["tables"]):
    #     rows = [" | ".join(str(c) for c in row if c) for row in table]
    #     chunks.append(f"[table {t_idx+1}]\n" + "\n".join(rows))

    return {**state, "pdf_context_snippet": "\n\n".join(chunks)}
