from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.control.agents.scanned_pdf_nodes.call_vision_llm import call_vision_llm
from src.control.agents.scanned_pdf_nodes.conditional_nodes.condition import (
    route_after_next_page,
    route_after_vision_llm,
)
from src.control.agents.scanned_pdf_nodes.load_pages import load_pages
from src.control.agents.scanned_pdf_nodes.next_page import next_page
from src.control.agents.state import ScannedPDFClassifierState


def build_scanned_subgraph() -> CompiledStateGraph[ScannedPDFClassifierState]:
    g = StateGraph(ScannedPDFClassifierState)

    g.add_node("load_pages", load_pages)
    g.add_node("next_page", next_page)
    g.add_node("call_vision_llm", call_vision_llm)

    g.set_entry_point("load_pages")
    g.add_edge("load_pages", "next_page")
    g.add_conditional_edges(
        "next_page",
        route_after_next_page,
        {"call_vision_llm": "call_vision_llm", "done": END},
    )
    g.add_conditional_edges(
        "call_vision_llm",
        route_after_vision_llm,
        {"next_page": "next_page", "done": END},
    )

    return g.compile()


scanned_subgraph = build_scanned_subgraph()
