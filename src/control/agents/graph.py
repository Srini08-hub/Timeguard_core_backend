import logging

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

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
from src.control.agents.nodes.scannedpdf_node import scannedpdfnode
from src.control.agents.state import TimeguardState

logger = logging.getLogger(__name__)

_email_graph: CompiledStateGraph[TimeguardState] | None = None


def build_email_graph() -> CompiledStateGraph[TimeguardState]:
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

    graph.set_entry_point("fetch_parse")

    graph.add_conditional_edges(
        "fetch_parse",
        classify_attachments_router,
        {
            "pdf_classifying_node": "pdf_classifying_node",
            "image_node": "image_node",
            "excel_node": "excel_node",
            "email_body_node": "email_body_node",
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

    graph.add_edge("digitalpdfnode", "increment_attachment_node")
    graph.add_edge("scannedpdfnode", "increment_attachment_node")
    graph.add_edge("hybridpdfnode", "increment_attachment_node")
    graph.add_edge("image_node", "increment_attachment_node")
    graph.add_edge("excel_node", "increment_attachment_node")

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

    graph.add_edge("email_body_node", END)

    return graph.compile()


def get_email_graph() -> CompiledStateGraph[TimeguardState]:
    global _email_graph
    if _email_graph is None:
        _email_graph = build_email_graph()
    return _email_graph
