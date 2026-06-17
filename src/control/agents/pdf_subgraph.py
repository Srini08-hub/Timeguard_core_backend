from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.control.agents.pdf_nodes.call_llm import call_llm
from src.control.agents.pdf_nodes.conditional_nodes.condition import (
    route_after_llm,
    route_anchor_found,
    route_page_has_content,
)
from src.control.agents.pdf_nodes.fuzzy_match_anchors import fuzzy_match_anchors
from src.control.agents.pdf_nodes.harvest_context import harvest_context
from src.control.agents.pdf_nodes.load_pdf import load_pdf
from src.control.agents.pdf_nodes.next_page import next_page
from src.control.agents.state import PDFClassifierState


def build_pdf_subgraph() -> CompiledStateGraph[PDFClassifierState]:
    g = StateGraph(PDFClassifierState)  # ← independent state

    g.add_node("load_pdf", load_pdf)
    g.add_node("next_page", next_page)
    g.add_node("fuzzy_match_anchors", fuzzy_match_anchors)
    g.add_node("harvest_context", harvest_context)
    g.add_node("call_llm", call_llm)

    g.set_entry_point("load_pdf")
    g.add_edge("load_pdf", "next_page")
    g.add_edge("harvest_context", "call_llm")

    # g.add_conditional_edges("next_page", route_pages_remaining, {
    #     "next_page": "next_page",
    #     "done":         END
    # })
    g.add_conditional_edges(
        "next_page",
        route_page_has_content,
        {"fuzzy_match_anchors": "fuzzy_match_anchors", "next_page": "next_page"},
    )
    g.add_conditional_edges(
        "fuzzy_match_anchors",
        route_anchor_found,
        {"harvest_context": "harvest_context", "next_page": "next_page"},
    )
    g.add_conditional_edges(
        "call_llm", route_after_llm, {"done": END, "next_page": "next_page"}
    )

    return g.compile()


pdf_subgraph = build_pdf_subgraph()  # built once at module level
