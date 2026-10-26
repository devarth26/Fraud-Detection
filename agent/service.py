"""Thin service layer: runs the graph, pauses/resumes human review, shapes API responses."""
from __future__ import annotations

import uuid

from langgraph.types import Command

from .graph import build_graph


class InvestigationService:
    def __init__(self, graph):
        self.graph = graph

    @classmethod
    def create(cls, **graph_kwargs) -> "InvestigationService":
        return cls(build_graph(**graph_kwargs))

    def investigate(self, query: str, transaction_id: int | None = None, transaction: dict | None = None) -> dict:
        thread_id = uuid.uuid4().hex
        config = {"configurable": {"thread_id": thread_id}}
        self.graph.invoke({"query": query, "transaction_id": transaction_id, "transaction": transaction}, config)
        return self._response(thread_id, config)

    def review(self, thread_id: str, decision: str, note: str = "") -> dict:
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = self.graph.get_state(config)
        if not snapshot.values:
            raise LookupError(f"Unknown investigation: {thread_id}")
        if not snapshot.next:
            raise ValueError("This investigation has no pending review.")
        self.graph.invoke(Command(resume={"decision": decision, "note": note}), config)
        return self._response(thread_id, config)

    def _response(self, thread_id: str, config: dict) -> dict:
        snap = self.graph.get_state(config)
        v = snap.values
        pending = bool(snap.next)
        review_request = None
        if pending:
            for task in snap.tasks:
                for itr in task.interrupts:
                    review_request = itr.value
        return {
            "thread_id": thread_id,
            "status": "pending_review" if pending else v.get("status", "completed"),
            "intent": v.get("intent"),
            "intent_source": v.get("intent_source"),
            "plan_source": v.get("plan_source"),
            "planned_tools": v.get("planned_tools", []),
            "tools_used": v.get("tools_used", []),
            "risk_tier": v.get("risk_tier"),
            "weighted_score": v.get("weighted_score"),
            "report": v.get("report"),
            "policies_cited": v.get("policies_cited", []),
            "policies_retrieved": [h["doc_id"] for h in v.get("policy_hits", [])],
            "narrative_source": v.get("narrative_source"),
            "review": v.get("review"),
            "review_request": review_request,
            "case_id": v.get("case_id"),
            "trace": v.get("trace", []),
        }
