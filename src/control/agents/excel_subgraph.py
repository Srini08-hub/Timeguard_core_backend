from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.control.agents.excel_nodes.call_llm import call_llm
from src.control.agents.excel_nodes.conditional_nodes.condition import (
    route_after_llm,
    route_anchor_found,
    route_sheet_has_content,
)
from src.control.agents.excel_nodes.fuzzy_matching import fuzzy_match_anchors
from src.control.agents.excel_nodes.harvest_context import harvest_context
from src.control.agents.excel_nodes.load_sheet import load_workbook_meta
from src.control.agents.excel_nodes.next_sheet import next_sheet
from src.control.agents.state import ExcelClassifierState


def build_excel_subgraph() -> CompiledStateGraph[ExcelClassifierState]:
    g = StateGraph(ExcelClassifierState)

    g.add_node("load_workbook_meta", load_workbook_meta)
    g.add_node("next_sheet", next_sheet)
    g.add_node("fuzzy_match_anchors", fuzzy_match_anchors)
    g.add_node("harvest_context", harvest_context)
    g.add_node("call_llm", call_llm)

    g.set_entry_point("load_workbook_meta")
    g.add_edge("load_workbook_meta", "next_sheet")
    g.add_edge("harvest_context", "call_llm")

    g.add_conditional_edges(
        "next_sheet",
        route_sheet_has_content,
        {
            "fuzzy_match_anchors": "fuzzy_match_anchors",
            "next_sheet": "next_sheet",
            "done": END,
        },
    )
    g.add_conditional_edges(
        "fuzzy_match_anchors",
        route_anchor_found,
        {"harvest_context": "harvest_context", "next_sheet": "next_sheet"},
    )
    g.add_conditional_edges(
        "call_llm", route_after_llm, {"done": END, "next_sheet": "next_sheet"}
    )

    return g.compile()


excel_subgraph = build_excel_subgraph()  # built once at module level
