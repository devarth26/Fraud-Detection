"""Side-effect-free scoring used by the agent and by the /score endpoint.

`/predict` (api/main.py) scores a transaction AND writes to the database AND calls the LLM.
An investigation agent must be able to re-score an existing transaction repeatedly without
creating duplicate rows or spending LLM calls, so this module exposes the same pipeline as a
pure function. It reuses the existing engine functions in api.main (rule engine, persona
classifier, orchestration) instead of copying them, so the agent can never drift from /predict.
"""
from __future__ import annotations

import zlib

EMPTY_CARD_STATS = {
    "tx_count": 0,
    "avg_amount": 0,
    "std_amount": 0,
    "dominant_merchant": 0,
    "dominant_location": 0,
    "merchant_diversity": 0,
    "location_diversity": 0,
    "avg_velocity": 0,
}


def stable_hash(value: str) -> int:
    """Deterministic string hash.

    Python's built-in hash() is randomised per process (PYTHONHASHSEED), so using it for
    card ids and categorical encodings means a card's history is lost on every restart.
    """
    return zlib.crc32(value.encode("utf-8")) & 0xFFFFFFFF


def card_id_for(device_match: str) -> int:
    # Same derivation /predict uses (hash(device_match) % 1000), but stable across restarts.
    # NOTE: the schema has no real card identifier yet; see docs/KNOWN_ISSUES.md.
    return stable_hash(device_match) % 1000


def history_encoders(transaction) -> dict:
    """Categorical encodings stored with each card_profiles row (see KNOWN_ISSUES.md)."""
    return {
        "merchant_enc": stable_hash(transaction.merchant_category) % 8,
        "location_enc": stable_hash(transaction.location) % 4,
        "time_enc": stable_hash(transaction.time_of_day) % 4,
        "device_enc": stable_hash(transaction.device_match) % 5,
    }


def score_transaction(transaction, db=None) -> dict:
    """Run the full FraudShield pipeline on one transaction without any side effects.

    transaction: api.schemas.TransactionInput
    db: optional SQLAlchemy session, used only for READING card history.
    """
    from . import main as engine  # lazy: importing main loads the ML artifacts

    card_id = card_id_for(transaction.device_match)
    history, card_stats = [], dict(EMPTY_CARD_STATS)
    if db is not None:
        from .database import get_card_history, get_card_stats

        history = get_card_history(db, card_id)
        card_stats = get_card_stats(db, card_id)

    ensemble = engine.predict_ensemble(transaction)
    lstm = engine.predict_lstm(transaction, history)
    autoencoder = engine.predict_autoencoder(transaction)
    rules = engine.rule_engine(transaction)
    orchestration = engine.orchestrate_risk(ensemble, lstm, autoencoder, rules)
    persona = engine.detect_fraud_persona(transaction, rules, ensemble, card_stats)

    return {
        "is_fraud": bool(orchestration["is_fraud"]),
        "risk_tier": orchestration["risk_tier"],
        "weighted_score": float(orchestration["weighted_score"]),
        "orchestration": orchestration,
        "rules": rules,
        "persona": persona,
        "card_stats": card_stats,
        "ensemble": {
            "verdict": ensemble["is_fraud"],
            "confidence": ensemble["confidence"],
            "votes": ensemble["votes"],
            "model_results": ensemble["model_results"],
        },
        "shap": ensemble["shap"],
        "lstm": {
            "verdict": lstm["fraud"],
            "confidence": lstm["confidence"],
            "attention_weights": lstm["attention_weights"],
        },
        "autoencoder": {
            "verdict": autoencoder["fraud"],
            "reconstruction_error": autoencoder["reconstruction_error"],
            "anomaly_score": autoencoder["anomaly_score"],
            "threshold": autoencoder["threshold"],
        },
    }
