"""Graph wiring.

START -> classify_query -> plan_tools -> run_data_tools -> retrieve_policy -> draft_report
      -> [HIGH risk] human_review (interrupt) -> finalize -> END
      -> [otherwise]                             finalize -> END
plan_tools / run_data_tools can end early with status "needs_input".
"""
from __future__ import annotations

import os

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .backends import Backends, default_backends
from .llm import get_llm
from .nodes import InvestigationNodes
from .state import InvestigationState

_USE_DEFAULT = object()


def make_checkpointer():
    """MemorySaver for one process. Set LANGGRAPH_POSTGRES_URL to persist paused reviews across
    restarts and across multiple container instances (required for a real deployment)."""
    url = os.getenv("LANGGRAPH_POSTGRES_URL")
    if not url:
        return MemorySaver()
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(url, kwargs={"autocommit": True, "prepare_threshold": 0}, open=True)
    saver = PostgresSaver(pool)
    saver.setup()
    return saver


def build_graph(backends: Backends | None = None, llm=_USE_DEFAULT, checkpointer=None):
    backends = backends or default_backends()
    llm = get_llm() if llm is _USE_DEFAULT else llm
    n = InvestigationNodes(backends, llm)

    g = StateGraph(InvestigationState)
    g.add_node("classify_query", n.classify_query)
    g.add_node("plan_tools", n.plan_tools)
    g.add_node("run_data_tools", n.run_data_tools)
    g.add_node("retrieve_policy", n.retrieve_policy)
    g.add_node("draft_report", n.draft_report)
    g.add_node("human_review", n.human_review)
    g.add_node("finalize", n.finalize)

    g.add_edge(START, "classify_query")
    g.add_edge("classify_query", "plan_tools")
    g.add_conditional_edges(
        "plan_tools",
        lambda s: END if s.get("needs_input") else "run_data_tools",
        {"run_data_tools": "run_data_tools", END: END},
    )
    g.add_conditional_edges(
        "run_data_tools",
        lambda s: END if s.get("needs_input") else "retrieve_policy",
        {"retrieve_policy": "retrieve_policy", END: END},
    )
    g.add_edge("retrieve_policy", "draft_report")
    g.add_conditional_edges(
        "draft_report",
        lambda s: "human_review" if s.get("needs_review") else "finalize",
        {"human_review": "human_review", "finalize": "finalize"},
    )
    g.add_edge("human_review", "finalize")
    g.add_edge("finalize", END)

    return g.compile(checkpointer=checkpointer or make_checkpointer())
