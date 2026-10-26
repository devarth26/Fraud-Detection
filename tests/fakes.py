"""Test doubles: fake models/DB/LLM, plus a REAL retriever over the real policy documents."""
from __future__ import annotations

from types import SimpleNamespace

from agent.backends import Backends
from rag.embeddings import HashingEmbeddings
from rag.retriever import PolicyRetriever

_retriever = None


def get_test_retriever():
    global _retriever
    if _retriever is None:
        _retriever = PolicyRetriever.build(embeddings=HashingEmbeddings())
    return _retriever


def make_score(tier="LOW", weighted=0.2, rules=None, persona_type="UNKNOWN", persona_label="No Fraud Pattern Detected"):
    return {
        "is_fraud": tier != "LOW",
        "risk_tier": tier,
        "weighted_score": weighted,
        "orchestration": {
            "weighted_score": weighted,
            "hard_override": tier == "HIGH",
            "override_reason": "EXTREME_AMOUNT_OVERRIDE" if tier == "HIGH" else None,
            "component_scores": {"ensemble": weighted, "lstm": weighted, "autoencoder": weighted, "rules": weighted},
        },
        "rules": {"rules_triggered": rules or [], "rule_count": len(rules or []), "score": weighted},
        "persona": {
            "primary_persona": {"type": persona_type, "label": persona_label, "severity": "HIGH" if tier == "HIGH" else "NONE"},
            "all_personas": [{"type": persona_type, "label": persona_label}] if persona_type != "UNKNOWN" else [],
        },
        "card_stats": {},
        "ensemble": {"verdict": tier != "LOW", "confidence": weighted, "votes": 4 if tier == "HIGH" else 0, "model_results": {}},
        "shap": {
            "top_features": [
                {"feature": "is_high_amount", "value": 1.0, "shap_value": 0.41, "direction": "fraud", "abs_impact": 0.41},
                {"feature": "card_age_months", "value": 24, "shap_value": -0.12, "direction": "legit", "abs_impact": 0.12},
            ],
            "base_value": -3.2,
            "total_shap": 0.3,
        },
        "lstm": {"verdict": False, "confidence": weighted, "attention_weights": []},
        "autoencoder": {"verdict": False, "reconstruction_error": 0.1, "anomaly_score": 0.1, "threshold": 1.0},
    }


def fake_score(tx: dict) -> dict:
    if tx["amount"] > 50000:
        return make_score("HIGH", 0.91, ["EXTREME_AMOUNT"], "MULE_ACTIVITY", "Money Mule / Laundering")
    if tx["amount"] < 1:
        return make_score("MEDIUM", 0.55, ["MICRO_TRANSACTION_CARD_TEST", "VELOCITY_SPIKE_CRITICAL"], "CARD_TESTING", "Card Testing Attack")
    return make_score("LOW", 0.12)


STORED_TX = {
    "amount": 120.0,
    "merchant_category": "Groceries",
    "location": "Same city",
    "time_of_day": "Evening",
    "transactions_last_24h": 1,
    "card_age_months": 30,
    "device_match": "Known device, matching IP",
}

LOW_TX = dict(STORED_TX)
HIGH_TX = {**STORED_TX, "amount": 75000.0, "merchant_category": "Online transfer", "location": "International"}
CARD_TEST_TX = {**STORED_TX, "amount": 0.5, "transactions_last_24h": 12, "card_age_months": 1, "merchant_category": "Electronics"}


class FakeBackends:
    def __init__(self, score_fn=fake_score, stored=None):
        self.saved_cases: list[dict] = []
        self.score_calls = 0
        self.stored = stored if stored is not None else {42: {**STORED_TX, "transaction_id": 42}, 43: {**HIGH_TX, "transaction_id": 43}}
        self._score_fn = score_fn

    def build(self) -> Backends:
        def score(tx):
            self.score_calls += 1
            return self._score_fn(tx)

        def save_case(data):
            self.saved_cases.append(data)
            return len(self.saved_cases)

        return Backends(
            get_transaction=lambda i: self.stored.get(i),
            score=score,
            card_history=lambda tx: {"tx_count": 0, "avg_amount": 0, "std_amount": 0, "dominant_merchant": 0,
                                     "dominant_location": 0, "merchant_diversity": 0, "location_diversity": 0, "avg_velocity": 0},
            search_policy=lambda q, k=4, rule_codes=None, personas=None: get_test_retriever().search(q, k=k, rule_codes=rule_codes, personas=personas),
            save_case=save_case,
        )


class FakeLLM:
    """Scripted LLM: fn(prompt) -> text."""

    def __init__(self, fn):
        self.fn = fn
        self.prompts: list[str] = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(content=self.fn(prompt))
