import asyncio
import logging
import sys

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Fix for Windows psycopg compatibility with async
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.config.settings import settings
from src.control.agents.digital_extract_node.digital_llm_extraction import (
    node_extract_block_with_llm as digital_node_extract_block_with_llm,
)
from src.control.agents.digital_extract_node.extract_node import (
    digital_pdf_extraction_node,
)
from src.control.agents.employee_matching_node.match_node import employee_matching_node
from src.control.agents.excel_extract_node.block_extraction import (
    node_extract_block_with_llm,
)
from src.control.agents.excel_extract_node.conndition_node.route_block import (
    increment_excel_block,
    route_next_block,
)
from src.control.agents.excel_extract_node.node_collect_result import (
    node_collect_results,
)
from src.control.agents.excel_extract_node.probe_extract import excel_extraction_node
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
from src.control.agents.excel_nodes.update_attachment_status import (
    update_excel_attachment_status,
)
from src.control.agents.extract_email_body_node.extract_node import (
    email_body_extraction_node,
)
from src.control.agents.hybrid_pdf_extract_node.hybrid_extract_node import (
    hybrid_pdf_extraction_node,
)
from src.control.agents.image_extract_node.extract_node import image_extraction_node
from src.control.agents.merge_node.merge_node import merge_node
from src.control.agents.nodes.classify_node import classify_attachments_router
from src.control.agents.nodes.digitalpdf_node import digitalpdfnode
from src.control.agents.nodes.email_body_node import email_body_node
from src.control.agents.nodes.excel_node import excelnode
from src.control.agents.nodes.fetchparse_node import fetch_parse_node
from src.control.agents.nodes.hybridpdf_node import hybridpdfnode
from src.control.agents.nodes.image_node import imagenode
from src.control.agents.nodes.incremental_node import increment_attachment_node
from src.control.agents.nodes.pdf_classifying_node import (
    pdf_classifying_node,
    route_pdf_classification,
)
from src.control.agents.nodes.route_afteremail import (
    increment_extraction_node,
    route_after_email_body,
)
from src.control.agents.nodes.scannedpdf_node import scannedpdfnode
from src.control.agents.pdf_nodes.call_llm import call_llm as pdf_call_llm
from src.control.agents.pdf_nodes.conditional_nodes.condition import (
    route_after_llm as pdf_route_after_llm,
)
from src.control.agents.pdf_nodes.conditional_nodes.condition import (
    route_anchor_found as pdf_route_anchor_found,
)
from src.control.agents.pdf_nodes.conditional_nodes.condition import (
    route_page_has_content,
)
from src.control.agents.pdf_nodes.fuzzy_match_anchors import (
    fuzzy_match_anchors as pdf_fuzzy_match_anchors,
)
from src.control.agents.pdf_nodes.harvest_context import (
    harvest_context as pdf_harvest_context,
)
from src.control.agents.pdf_nodes.load_pdf import load_pdf
from src.control.agents.pdf_nodes.next_page import next_page
from src.control.agents.pdf_nodes.update_attachment_status import (
    update_pdf_attachment_status,
)
from src.control.agents.scanned_pdf_extraction_node.extract_node import (
    scanned_pdf_extraction_node,
)
from src.control.agents.scanned_pdf_nodes.call_vision_llm import call_vision_llm
from src.control.agents.scanned_pdf_nodes.conditional_nodes.condition import (
    route_after_next_page,
    route_after_vision_llm,
)
from src.control.agents.scanned_pdf_nodes.load_pages import load_pages
from src.control.agents.scanned_pdf_nodes.next_page import (
    next_page as scanned_next_page,
)
from src.control.agents.scanned_pdf_nodes.update_attachment_status import (
    update_scanned_pdf_attachment_status,
)
from src.control.agents.state import TimeguardState
from src.control.agents.validation_nodes import validation_node

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# _email_graph: CompiledStateGraph[TimeguardState] | None = None
# _checkpointer: AsyncPostgresSaver | None = None


# async def get_checkpointer() -> AsyncPostgresSaver:
#     global _checkpointer
#     if _checkpointer is None:
#         _checkpointer = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URI)
#         await _checkpointer.setup()
#     return _checkpointer

_email_graph: CompiledStateGraph[TimeguardState] | None = None
_checkpointer: AsyncPostgresSaver | None = None
_checkpointer_cm = None  # holds the context manager so it isn't garbage collected / closed


async def get_checkpointer() -> AsyncPostgresSaver:
    global _checkpointer, _checkpointer_cm
    if _checkpointer is None:
        _checkpointer_cm = AsyncPostgresSaver.from_conn_string(settings.SYNC_DATABASE_URI)
        _checkpointer = await _checkpointer_cm.__aenter__()
        await _checkpointer.setup()
    return _checkpointer


# async def dummy_extraction_node(state: TimeguardState) -> TimeguardState:
#     logger.info("Dummy extraction node executed")
#     return state


async def build_email_graph() -> CompiledStateGraph[TimeguardState]:
    graph = StateGraph(TimeguardState)

    graph.add_node("fetch_parse", fetch_parse_node)
    graph.add_node("pdf_classifying_node", pdf_classifying_node)
    graph.add_node("digitalpdfnode", digitalpdfnode)
    graph.add_node("scannedpdfnode", scannedpdfnode)
    graph.add_node("hybridpdfnode", hybridpdfnode)
    graph.add_node("increment_attachment_node", increment_attachment_node)
    graph.add_node("image_node", imagenode)
    graph.add_node("excel_node", excelnode)
    graph.add_node("email_body_node", email_body_node)
    graph.add_node("digital_pdf_extraction_node", digital_pdf_extraction_node)
    graph.add_node("digital_node_extract_block_with_llm", digital_node_extract_block_with_llm)
    # graph.add_node("digital_odf_extraction_node", dummy_extraction_node)
    graph.add_node("excel_extraction_node", excel_extraction_node)
    graph.add_node("scanned_pdf_extraction_node", scanned_pdf_extraction_node)
    graph.add_node("image_extraction_node", image_extraction_node)
    graph.add_node("hybrid_pdf_extraction_node", hybrid_pdf_extraction_node)
    graph.add_node("email_body_extraction_node", email_body_extraction_node)
    graph.add_node("merge_node", merge_node)
    # graph.add_node("email_extraction_node", dummy_extraction_node)

    # Excel classification nodes (from excel_subgraph)
    graph.add_node("load_workbook_meta", load_workbook_meta)
    graph.add_node("next_sheet", next_sheet)
    graph.add_node("fuzzy_match_anchors", fuzzy_match_anchors)
    graph.add_node("harvest_context", harvest_context)
    graph.add_node("call_llm", call_llm)
    graph.add_node("update_excel_attachment_status", update_excel_attachment_status)

    # PDF classification nodes (from pdf_subgraph)
    graph.add_node("load_pdf", load_pdf)
    graph.add_node("next_page", next_page)
    graph.add_node("pdf_fuzzy_match_anchors", pdf_fuzzy_match_anchors)
    graph.add_node("pdf_harvest_context", pdf_harvest_context)
    graph.add_node("pdf_call_llm", pdf_call_llm)
    graph.add_node("update_pdf_attachment_status", update_pdf_attachment_status)

    # Scanned PDF classification nodes (from scanned_subgraph)
    graph.add_node("scanned_load_pages", load_pages)
    graph.add_node("scanned_next_page", scanned_next_page)
    graph.add_node("scanned_call_vision_llm", call_vision_llm)  # async node with config
    graph.add_node(
        "update_scanned_pdf_attachment_status", update_scanned_pdf_attachment_status
    )
    graph.add_node("increment_extraction_node", increment_extraction_node)
    graph.add_node("increment_excel_block", increment_excel_block)
    graph.set_entry_point("fetch_parse")

    graph.add_conditional_edges(
        "fetch_parse",
        classify_attachments_router,
        {
            "pdf_classifying_node": "pdf_classifying_node",
            "image_node": "image_node",
            "load_workbook": "load_workbook_meta",
            "email_body_node": "email_body_node",
            "excel_node": "excel_node",
        },
    )

    graph.add_conditional_edges(
        "pdf_classifying_node",
        route_pdf_classification,
        {
            "digitalpdfnode": "digitalpdfnode",
            "scannedpdfnode": "scannedpdfnode",
            "hybridpdfnode": "hybridpdfnode",
            "increment_attachment_node": "increment_attachment_node",
        },
    )
    graph.add_edge("digitalpdfnode", "load_pdf")
    graph.add_edge("scannedpdfnode", "scanned_load_pages")
    graph.add_edge("excel_node", "load_workbook_meta")
    graph.add_edge("image_node", "increment_attachment_node")
    graph.add_edge("hybridpdfnode", "increment_attachment_node")
    # graph.add_edge("load_workbook_meta", "increment_attachment_node")

    # PDF classification subgraph edges
    graph.add_edge("load_pdf", "next_page")
    graph.add_edge("pdf_harvest_context", "pdf_call_llm")

    graph.add_conditional_edges(
        "next_page",
        route_page_has_content,
        {"pdf_fuzzy_match_anchors": "pdf_fuzzy_match_anchors", "next_page": "next_page"},
    )
    graph.add_conditional_edges(
        "pdf_fuzzy_match_anchors",
        pdf_route_anchor_found,
        {"pdf_harvest_context": "pdf_harvest_context", "next_page": "next_page"},
    )
    graph.add_conditional_edges(
        "pdf_call_llm",
        pdf_route_after_llm,
        {"done": "update_pdf_attachment_status", "next_page": "next_page"},
    )
    graph.add_edge("update_pdf_attachment_status", "increment_attachment_node")

    # Scanned PDF classification subgraph edges
    graph.add_edge("scanned_load_pages", "scanned_next_page")
    graph.add_conditional_edges(
        "scanned_next_page",
        route_after_next_page,
        {
            "scanned_call_vision_llm": "scanned_call_vision_llm",
            "done": "increment_attachment_node",
        },
    )
    graph.add_conditional_edges(
        "scanned_call_vision_llm",
        route_after_vision_llm,
        {
            "scanned_next_page": "scanned_next_page",
            "done": "update_scanned_pdf_attachment_status",
        },
    )
    graph.add_edge("update_scanned_pdf_attachment_status", "increment_attachment_node")

    # Excel classification subgraph edges
    graph.add_edge("load_workbook_meta", "next_sheet")
    graph.add_edge("harvest_context", "call_llm")

    graph.add_conditional_edges(
        "next_sheet",
        route_sheet_has_content,
        {
            "fuzzy_match_anchors": "fuzzy_match_anchors",
            "next_sheet": "next_sheet",
            "done": "increment_attachment_node",
        },
    )
    graph.add_conditional_edges(
        "fuzzy_match_anchors",
        route_anchor_found,
        {"harvest_context": "harvest_context", "next_sheet": "next_sheet"},
    )
    graph.add_conditional_edges(
        "call_llm",
        route_after_llm,
        {"done": "update_excel_attachment_status", "next_sheet": "next_sheet"},
    )
    graph.add_edge("update_excel_attachment_status", "increment_attachment_node")

    graph.add_conditional_edges(
        "increment_attachment_node",
        classify_attachments_router,
        {
            "pdf_classifying_node": "pdf_classifying_node",
            "image_node": "image_node",
            "excel_node": "excel_node",
            "email_body_node": "email_body_node",
        },
    )
    # graph.add_edge("email_body_node",END)

    graph.add_conditional_edges(
        "email_body_node",
        route_after_email_body,
        {
            "digital_pdf_extraction_node": "digital_pdf_extraction_node",
            "scanned_pdf_extraction_node": "scanned_pdf_extraction_node",
            "image_extraction_node": "image_extraction_node",
            "excel_extraction_node": "excel_extraction_node",
            "email_body_extraction_node": "email_body_extraction_node",
            "hybrid_pdf_extraction_node": "hybrid_pdf_extraction_node",
            "increment_extraction_node": "increment_extraction_node",
            "end": END,
        },
    )

    # graph.add_node("excel_extraction_node", excel_extraction_node)
    graph.add_node("extract_block_with_llm", node_extract_block_with_llm)
    graph.add_conditional_edges(
        "excel_extraction_node",
        route_next_block,
        {
            "extract_block_with_llm": "extract_block_with_llm",
            "collect_results": "collect_results",
        },
    )

    graph.add_node("collect_results", node_collect_results)
    graph.add_edge("extract_block_with_llm", "increment_excel_block")
    graph.add_conditional_edges(
        "increment_excel_block",
        route_next_block,
        {
            "extract_block_with_llm": "extract_block_with_llm",
            "collect_results": "collect_results",
        },
    )
    graph.add_edge("collect_results", "increment_extraction_node")
    graph.add_edge("digital_pdf_extraction_node", "digital_node_extract_block_with_llm")
    graph.add_edge("digital_node_extract_block_with_llm", "increment_extraction_node")
    graph.add_edge("scanned_pdf_extraction_node", "increment_extraction_node")
    graph.add_edge("hybrid_pdf_extraction_node", "increment_extraction_node")
    graph.add_edge("image_extraction_node", "increment_extraction_node")
    # graph.add_edge("email_body_extraction_node", "increment_extraction_node")
    # graph.add_edge("email_extraction_node", "increment_extraction_node")
    graph.add_edge("email_body_extraction_node", "merge_node")
    graph.add_node("employee_matching_node", employee_matching_node)
    graph.add_edge("merge_node", "employee_matching_node")
    graph.add_node("validation_node", validation_node)
    graph.add_edge("employee_matching_node", "validation_node")
    graph.add_edge("validation_node", END)

    graph.add_conditional_edges(
        "increment_extraction_node",
        route_after_email_body,
        {
            "digital_pdf_extraction_node": "digital_pdf_extraction_node",
            "scanned_pdf_extraction_node": "scanned_pdf_extraction_node",
            "hybrid_pdf_extraction_node": "hybrid_pdf_extraction_node",
            "image_extraction_node": "image_extraction_node",
            "excel_extraction_node": "excel_extraction_node",
            "email_body_extraction_node": "email_body_extraction_node",
            "increment_extraction_node": "increment_extraction_node",
            "merge_node": "merge_node",
            "end": END,
        },
    )

    checkpointer = await get_checkpointer()
    return graph.compile(checkpointer=checkpointer)


async def get_email_graph() -> CompiledStateGraph[TimeguardState]:
    global _email_graph
    if _email_graph is None:
        _email_graph = await build_email_graph()
    return _email_graph
