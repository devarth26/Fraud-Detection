import subprocess
import sys
import types

from api.scoring import card_id_for, history_encoders, score_transaction, stable_hash

from .fakes import make_score


def test_stable_hash_is_identical_across_processes_with_different_hash_seeds():
    code = "from api.scoring import stable_hash; print(stable_hash('VPN / proxy detected'))"
    outs = {
        subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       env={"PYTHONHASHSEED": seed, "PYTHONPATH": ".", "DATABASE_URL": "sqlite://", "PATH": ""}).stdout.strip()
        for seed in ("1", "2", "3")
    }
    assert len(outs) == 1 and outs != {""}
    assert str(stable_hash("VPN / proxy detected")) in outs


def test_card_id_and_encoders_in_range():
    assert 0 <= card_id_for("New device, new IP") < 1000
    tx = types.SimpleNamespace(merchant_category="Groceries", location="Same city", time_of_day="Evening", device_match="Known device, matching IP")
    enc = history_encoders(tx)
    assert 0 <= enc["merchant_enc"] < 8 and 0 <= enc["location_enc"] < 4
    assert 0 <= enc["time_enc"] < 4 and 0 <= enc["device_enc"] < 5


def test_score_transaction_runs_pipeline_without_db_or_llm(monkeypatch):
    calls = []
    s = make_score("HIGH", 0.9, ["EXTREME_AMOUNT"])
    fake_main = types.SimpleNamespace(
        predict_ensemble=lambda t: calls.append("ens") or {"is_fraud": True, "confidence": 0.9, "votes": 4, "model_results": {}, "shap": s["shap"]},
        predict_lstm=lambda t, h: calls.append("lstm") or {"fraud": True, "confidence": 0.8, "attention_weights": []},
        predict_autoencoder=lambda t: calls.append("ae") or {"fraud": True, "reconstruction_error": 1.0, "anomaly_score": 1.0, "threshold": 1.0},
        rule_engine=lambda t: {"score": 1.0, "rules_triggered": ["EXTREME_AMOUNT"], "rule_count": 1},
        orchestrate_risk=lambda e, l, a, r: {"is_fraud": True, "risk_tier": "HIGH", "weighted_score": 0.9, "hard_override": True,
                                              "override_reason": "EXTREME_AMOUNT_OVERRIDE", "component_scores": {}},
        detect_fraud_persona=lambda t, r, e, c: {"primary_persona": {"type": "UNKNOWN"}, "all_personas": []},
    )
    monkeypatch.setitem(sys.modules, "api.main", fake_main)
    tx = types.SimpleNamespace(device_match="VPN / proxy detected")
    out = score_transaction(tx, db=None)
    assert out["risk_tier"] == "HIGH" and out["weighted_score"] == 0.9
    assert calls == ["ens", "lstm", "ae"]
    assert set(out) >= {"rules", "persona", "ensemble", "shap", "lstm", "autoencoder", "card_stats", "orchestration"}


def test_to_native_converts_numpy_and_decimal_recursively():
    from decimal import Decimal

    import numpy as np

    from api.scoring import to_native

    out = to_native({"a": np.float64(1.5), "b": [np.int64(2), np.bool_(True)], "c": {"d": np.array([1.0, 2.0])}, "e": Decimal("3.5"), "f": "x"})
    assert out == {"a": 1.5, "b": [2, True], "c": {"d": [1.0, 2.0]}, "e": 3.5, "f": "x"}
    assert type(out["a"]) is float and type(out["b"][0]) is int and type(out["b"][1]) is bool
