"""The agent's tools, as LangChain StructuredTools. Nodes execute them through .invoke(), so the
same objects provide the schemas shown to the planner and the code that runs."""
from __future__ import annotations

from langchain_core.tools import StructuredTool

from api.scoring import to_native

from .backends import Backends

TOOL_DESCRIPTIONS = {
    "lookup_transaction": "SQL lookup of a stored transaction by id in PostgreSQL. Needed only when the analyst gives a transaction id instead of transaction details.",
    "score_transaction": "Run the FraudShield models (ensemble, BiLSTM, autoencoder, rule engine) and return risk tier, weighted score, triggered rules and fraud persona.",
    "explain_shap": "Explain which features pushed the model toward fraud or legit, using SHAP values from the score. Use for 'why was this flagged' questions.",
    "get_card_history": "Fetch the card's behavioural baseline (average spend, velocity, merchant and location diversity) from PostgreSQL.",
    "search_policy": "Retrieve relevant fraud policy sections and past case notes (RAG). Use for 'what should I do' or policy questions.",
}


def summarise_shap(shap: dict | None, top_n: int = 5) -> dict:
    if not shap or shap.get("error") or not shap.get("top_features"):
        return {"available": False, "top_features": [], "narrative": "SHAP explanation unavailable for this transaction."}
    feats = shap["top_features"][:top_n]
    toward_fraud = [f for f in feats if f["direction"] == "fraud"]
    toward_legit = [f for f in feats if f["direction"] == "legit"]

    def fmt(items):
        return ", ".join(f"{f['feature']}={f['value']} ({f['shap_value']:+.3f})" for f in items) or "none"

    narrative = (
        f"Features pushing toward fraud: {fmt(toward_fraud)}. "
        f"Features pushing toward legitimate: {fmt(toward_legit)}."
    )
    return {"available": True, "base_value": shap.get("base_value"), "top_features": feats, "narrative": narrative}


def build_tools(b: Backends) -> dict[str, StructuredTool]:
    def lookup_transaction(transaction_id: int) -> dict:
        return to_native(b.get_transaction(transaction_id) or {})

    def score_transaction(transaction: dict) -> dict:
        return to_native(b.score(transaction))

    def explain_shap(score: dict) -> dict:
        return summarise_shap(score.get("shap"))

    def get_card_history(transaction: dict) -> dict:
        return to_native(b.card_history(transaction))

    def search_policy(query: str, rule_codes: list[str] | None = None, personas: list[str] | None = None, k: int = 4) -> list:
        return to_native(b.search_policy(query, k=k, rule_codes=rule_codes or [], personas=personas or []))

    funcs = [lookup_transaction, score_transaction, explain_shap, get_card_history, search_policy]
    return {
        f.__name__: StructuredTool.from_function(f, name=f.__name__, description=TOOL_DESCRIPTIONS[f.__name__])
        for f in funcs
    }
