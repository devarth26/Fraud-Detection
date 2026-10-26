"""Everything the agent touches outside itself, behind one injectable interface.

Production wiring (default_backends) uses PostgreSQL, the FraudShield models and the policy
retriever. Tests and the offline evaluation inject fakes, so the graph logic can be tested
without a database, model artifacts or an API key.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

TX_FIELDS = [
    "amount",
    "merchant_category",
    "location",
    "time_of_day",
    "transactions_last_24h",
    "card_age_months",
    "device_match",
]


@dataclass
class Backends:
    get_transaction: Callable[[int], Optional[dict]]
    score: Callable[[dict], dict]
    card_history: Callable[[dict], dict]
    search_policy: Callable[..., list]
    save_case: Callable[[dict], Optional[int]]


_retriever = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        from rag.retriever import PolicyRetriever

        _retriever = PolicyRetriever.build()
    return _retriever


def default_backends() -> Backends:
    from api.database import SessionLocal, Transaction
    from api.schemas import TransactionInput
    from api.scoring import EMPTY_CARD_STATS, card_id_for, score_transaction

    from .cases import save_case

    def get_transaction(transaction_id: int) -> Optional[dict]:
        with SessionLocal() as db:
            row = db.query(Transaction).filter(Transaction.id == transaction_id).first()
            if row is None:
                return None
            data = {f: getattr(row, f) for f in TX_FIELDS}
            data["transaction_id"] = row.id
            data["stored_verdict"] = {
                "is_fraud": row.is_fraud,
                "confidence": row.confidence,
                "risk_tier": row.risk_tier,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            }
            return data

    def score(tx: dict) -> dict:
        ti = TransactionInput(**{f: tx[f] for f in TX_FIELDS})
        with SessionLocal() as db:
            return score_transaction(ti, db)

    def card_history(tx: dict) -> dict:
        from api.database import get_card_stats

        try:
            with SessionLocal() as db:
                return get_card_stats(db, card_id_for(tx["device_match"]))
        except Exception:
            return dict(EMPTY_CARD_STATS)

    def search_policy(query, k=4, rule_codes=None, personas=None):
        return _get_retriever().search(query, k=k, rule_codes=rule_codes, personas=personas)

    return Backends(
        get_transaction=get_transaction,
        score=score,
        card_history=card_history,
        search_policy=search_policy,
        save_case=save_case,
    )
