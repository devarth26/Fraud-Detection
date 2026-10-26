"""LangGraph node implementations. Dependencies (backends, llm) are injected so every node can be
tested with fakes."""
from __future__ import annotations

import os

from langgraph.types import interrupt

from .backends import Backends
from .planner import NEEDS_TRANSACTION, choose_tools, classify_intent, enforce_dependencies, extract_transaction_id
from .report import (
    assemble_report,
    build_facts,
    extract_citations,
    llm_narrative,
    review_section,
    sanitize_citations,
    template_narrative,
)
from .state import InvestigationState
from .tools import build_tools

REVIEW_THRESHOLD = float(os.getenv("REVIEW_THRESHOLD", "0.75"))
VALID_DECISIONS = ("approve", "escalate", "dismiss")


def requires_review(state: dict) -> bool:
    """HIGH risk or weighted score at/above the threshold needs a human decision (POL-010)."""
    if not state.get("score"):
        return False
    return state.get("risk_tier") == "HIGH" or (state.get("weighted_score") or 0.0) >= REVIEW_THRESHOLD


class InvestigationNodes:
    def __init__(self, backends: Backends, llm):
        self.b = backends
        self.llm = llm
        self.tools = build_tools(backends)

    # 1. classify ---------------------------------------------------------------------------
    def classify_query(self, state: InvestigationState) -> dict:
        tx_id = state.get("transaction_id")
        if tx_id is None and not state.get("transaction"):
            tx_id = extract_transaction_id(state["query"])
        has_tx = bool(state.get("transaction")) or tx_id is not None
        intent, source = classify_intent(self.llm, state["query"], has_tx)
        return {
            "transaction_id": tx_id,
            "intent": intent,
            "intent_source": source,
            "trace": [f"classify_query: intent={intent} ({source})"],
        }

    # 2. plan ---------------------------------------------------------------------------------
    def plan_tools(self, state: InvestigationState) -> dict:
        has_inline = bool(state.get("transaction"))
        has_any_tx = has_inline or state.get("transaction_id") is not None
        tools, source = choose_tools(self.llm, state["query"], state["intent"])
        if not has_any_tx and state["intent"] == "policy_question":
            tools = [t for t in tools if t not in NEEDS_TRANSACTION] or ["search_policy"]
        ordered, needs_input = enforce_dependencies(tools, has_inline, state.get("transaction_id"))
        if needs_input:
            return {
                "planned_tools": [],
                "plan_source": source,
                "needs_input": needs_input,
                "status": "needs_input",
                "report": needs_input,
                "trace": [f"plan_tools: cannot proceed - {needs_input}"],
            }
        return {
            "planned_tools": ordered,
            "plan_source": source,
            "trace": [f"plan_tools: {ordered} ({source})"],
        }

    # 3. data tools ---------------------------------------------------------------------------
    def run_data_tools(self, state: InvestigationState) -> dict:
        planned = state["planned_tools"]
        out: dict = {}
        used: list[str] = []
        trace: list[str] = []
        tx = state.get("transaction")

        if "lookup_transaction" in planned:
            used.append("lookup_transaction")
            tx = self.tools["lookup_transaction"].invoke({"transaction_id": state["transaction_id"]})
            if not tx:
                msg = f"Transaction {state['transaction_id']} was not found."
                return {
                    "needs_input": msg,
                    "status": "needs_input",
                    "report": msg,
                    "tools_used": used,
                    "trace": ["lookup_transaction: not found"],
                }
            out["transaction"] = tx
            trace.append(f"lookup_transaction: found id={state['transaction_id']}")

        score = None
        if "score_transaction" in planned and tx:
            used.append("score_transaction")
            try:
                score = self.tools["score_transaction"].invoke({"transaction": tx})
                out.update(score=score, risk_tier=score["risk_tier"], weighted_score=score["weighted_score"])
                trace.append(f"score_transaction: {score['risk_tier']} {score['weighted_score']:.2f}")
            except Exception as exc:  # keep going: the report states what is unavailable
                trace.append(f"score_transaction FAILED: {exc}")

        if "explain_shap" in planned and score:
            used.append("explain_shap")
            out["shap"] = self.tools["explain_shap"].invoke({"score": score})
            trace.append("explain_shap: done")

        if "get_card_history" in planned and tx:
            used.append("get_card_history")
            try:
                out["card_history"] = self.tools["get_card_history"].invoke({"transaction": tx})
                trace.append(f"get_card_history: {out['card_history'].get('tx_count', 0)} prior transactions")
            except Exception as exc:
                trace.append(f"get_card_history FAILED: {exc}")

        out["tools_used"] = used
        out["trace"] = trace
        return out

    # 4. retrieve -----------------------------------------------------------------------------
    def retrieve_policy(self, state: InvestigationState) -> dict:
        if "search_policy" not in state["planned_tools"]:
            return {"policy_hits": [], "trace": ["retrieve_policy: skipped"]}
        score = state.get("score")
        rules = score["rules"]["rules_triggered"] if score else []
        personas = [p["type"] for p in score["persona"]["all_personas"]] if score else []
        parts = [state["query"]]
        if score:
            # Every detected persona is evidence, not just the top-ranked one: persona ranking can
            # be wrong when the card has no history, and retrieval should not inherit that error.
            labels = [p["label"] for p in score["persona"]["all_personas"] if p.get("label")]
            parts += labels or [score["persona"]["primary_persona"]["label"]]
            parts += [r.replace("_", " ").lower() for r in rules]
        hits = self.tools["search_policy"].invoke(
            {"query": " ".join(parts), "rule_codes": rules, "personas": personas, "k": 4}
        )
        return {
            "policy_hits": hits,
            "tools_used": ["search_policy"],
            "trace": [f"retrieve_policy: {[h['doc_id'] for h in hits]}"],
        }

    # 5. draft --------------------------------------------------------------------------------
    def draft_report(self, state: InvestigationState) -> dict:
        working = {**state, "needs_review": requires_review(state)}
        narrative = llm_narrative(self.llm, working, build_facts(working)) if self.llm else None
        source = "llm" if narrative else "template"
        if narrative is None:
            narrative = template_narrative(working)
        allowed = {h["doc_id"] for h in working.get("policy_hits", [])}
        narrative, removed = sanitize_citations(narrative, allowed)
        cited = [c for c in extract_citations(narrative) if c in allowed]
        trace = [f"draft_report: narrative={source}, cited={cited}"]
        if removed:
            trace.append(f"draft_report: removed unverified references {removed}")
        return {
            "report": assemble_report(working, narrative),
            "policies_cited": cited,
            "narrative_source": source,
            "needs_review": working["needs_review"],
            "trace": trace,
        }

    # 6. human review (pauses the graph until an analyst responds) ----------------------------
    def human_review(self, state: InvestigationState) -> dict:
        answer = interrupt(
            {
                "type": "analyst_review",
                "transaction_id": state.get("transaction_id"),
                "risk_tier": state.get("risk_tier"),
                "weighted_score": state.get("weighted_score"),
                "report_preview": state.get("report"),
                "options": list(VALID_DECISIONS),
            }
        )
        decision = str(answer.get("decision", "")).lower() if isinstance(answer, dict) else ""
        note = str(answer.get("note", "")) if isinstance(answer, dict) else ""
        if decision not in VALID_DECISIONS:
            decision, note = "escalate", f"Invalid decision defaulted to escalate. {note}".strip()
        review = {"decision": decision, "note": note}
        return {
            "review": review,
            "report": state["report"] + "\n\n" + review_section(review),
            "trace": [f"human_review: {decision}"],
        }

    # 7. finalize -----------------------------------------------------------------------------
    def finalize(self, state: InvestigationState) -> dict:
        status = "reviewed" if state.get("review") else "completed"
        case_id = None
        if state.get("transaction") or state.get("transaction_id") is not None:
            try:
                case_id = self.b.save_case({**state, "status": status})
            except Exception as exc:
                return {"status": status, "case_id": None, "trace": [f"finalize: case not saved ({exc})"]}
        return {"status": status, "case_id": case_id, "trace": [f"finalize: {status}, case_id={case_id}"]}
