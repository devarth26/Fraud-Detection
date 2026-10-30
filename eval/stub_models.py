"""Deterministic stand-in for api.model, for exercising the pipeline WITHOUT the trained artifacts.

Scores here are NOT real model outputs. The rule engine, persona classifier and orchestration in
api.main are real, so rules/personas/risk tiers are realistic, but never quote metrics produced
with --stub-models as model performance.
"""
from __future__ import annotations

import sys
import types

HIGH_RISK_MERCHANTS = {"Crypto exchange", "ATM withdrawal", "Online transfer"}


def _risk(t) -> float:
    s = 0.03
    s += 0.30 if t.amount > 5000 else 0
    s += 0.30 if t.amount < 1 else 0
    s += 0.20 if t.transactions_last_24h > 5 else 0
    s += 0.15 if t.card_age_months < 6 else 0
    s += 0.20 if "VPN" in t.device_match else 0
    s += 0.10 if "New device" in t.device_match else 0
    s += 0.15 if t.location in ("International", "High-risk country") else 0
    s += 0.15 if t.merchant_category in HIGH_RISK_MERCHANTS else 0
    return min(0.98, s)


def predict_ensemble(t):
    p = _risk(t)
    votes = 5 if p > 0.8 else 3 if p > 0.5 else 0
    flag = p >= 0.5
    return {
        "is_fraud": votes >= 3, "confidence": round(p, 4), "votes": votes,
        "model_results": {
            "xgboost": {"fraud": flag, "confidence": round(p, 4)},
            "random_forest": {"fraud": flag, "confidence": round(p * 0.95, 4)},
            "logistic_regression": {"fraud": flag, "confidence": round(p * 0.9, 4)},
            "gradient_boosting": {"fraud": flag, "confidence": round(p * 0.97, 4)},
            "isolation_forest": {"fraud": flag, "confidence": None},
        },
        "shap": {
            "top_features": [
                {"feature": "is_high_amount", "value": float(t.amount > 5000), "shap_value": 0.30 if t.amount > 5000 else -0.05,
                 "direction": "fraud" if t.amount > 5000 else "legit", "abs_impact": 0.3},
                {"feature": "card_age_months", "value": t.card_age_months, "shap_value": 0.2 if t.card_age_months < 6 else -0.1,
                 "direction": "fraud" if t.card_age_months < 6 else "legit", "abs_impact": 0.2},
            ],
            "base_value": -3.0, "total_shap": 0.0,
        },
    }


def predict_lstm(t, history):
    p = _risk(t) * 0.9
    return {"fraud": p >= 0.5, "confidence": round(p, 4), "attention_weights": [0.1] * 10}


def predict_autoencoder(t):
    p = _risk(t)
    return {"fraud": p >= 0.5, "reconstruction_error": round(p, 4), "threshold": 0.5, "anomaly_score": round(min(p / 0.5, 2.0), 4)}


def install():
    """Register the stub as `api.model` so importing api.main does not load .pkl/.pt artifacts."""
    mod = types.ModuleType("api.model")
    mod.predict_ensemble, mod.predict_lstm, mod.predict_autoencoder = predict_ensemble, predict_lstm, predict_autoencoder
    sys.modules["api.model"] = mod
