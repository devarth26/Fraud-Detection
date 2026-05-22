from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
import os
import json
from pathlib import Path
from .schemas import TransactionInput
from .model import predict_ensemble, predict_lstm, predict_autoencoder
from .database import get_db, Transaction, CardProfile, get_card_history, save_card_history, get_card_stats

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = FastAPI(title="FraudShield API", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


def rule_engine(transaction: TransactionInput) -> dict:
    rules_triggered = []
    rule_score = 0.0

    if transaction.amount > 50000:
        rules_triggered.append("EXTREME_AMOUNT")
        rule_score += 1.0
    elif transaction.amount > 10000:
        rules_triggered.append("HIGH_AMOUNT")
        rule_score += 0.5
    elif transaction.amount < 1.0:
        rules_triggered.append("MICRO_TRANSACTION_CARD_TEST")
        rule_score += 0.6

    if transaction.transactions_last_24h >= 10:
        rules_triggered.append("VELOCITY_SPIKE_CRITICAL")
        rule_score += 0.8
    elif transaction.transactions_last_24h >= 6:
        rules_triggered.append("VELOCITY_ELEVATED")
        rule_score += 0.4

    if transaction.card_age_months < 3:
        rules_triggered.append("NEW_CARD_HIGH_RISK")
        rule_score += 0.5
    elif transaction.card_age_months < 6:
        rules_triggered.append("NEW_CARD_ELEVATED")
        rule_score += 0.2

    is_vpn       = "VPN" in transaction.device_match
    is_high_risk = "High-risk" in transaction.location
    is_new_dev   = "New device" in transaction.device_match
    if is_vpn and is_high_risk and is_new_dev:
        rules_triggered.append("TRIPLE_THREAT_VPN_LOCATION_DEVICE")
        rule_score += 1.0

    is_crypto = transaction.merchant_category == "Crypto exchange"
    is_intl   = transaction.location in ["International", "High-risk country"]
    is_new    = transaction.card_age_months < 6
    if is_crypto and is_intl and is_new:
        rules_triggered.append("CRYPTO_NEWCARD_INTERNATIONAL")
        rule_score += 0.9

    is_late = "Late night" in transaction.time_of_day
    is_high = transaction.amount > 5000
    if is_late and is_high:
        rules_triggered.append("LATE_NIGHT_HIGH_AMOUNT")
        rule_score += 0.4
    elif is_vpn and not is_high_risk:
        rules_triggered.append("VPN_DETECTED")
        rule_score += 0.3

    return {
        "score":           round(min(rule_score, 1.0), 4),
        "rules_triggered": rules_triggered,
        "rule_count":      len(rules_triggered)
    }

def detect_fraud_persona(transaction: TransactionInput, rules: dict, ensemble: dict, card_stats: dict) -> dict:
    """
    Classifies the TYPE of fraud based on transaction patterns.
    Goes beyond probability to explain the attack vector.
    """
    triggered = rules["rules_triggered"]
    amount    = transaction.amount
    velocity  = transaction.transactions_last_24h
    card_age  = transaction.card_age_months
    is_vpn    = "VPN" in transaction.device_match
    is_new_dev = "New device" in transaction.device_match
    is_crypto  = transaction.merchant_category == "Crypto exchange"
    is_intl    = transaction.location in ["International", "High-risk country"]
    is_late    = "Late night" in transaction.time_of_day
    avg_amount = card_stats.get("avg_amount", 0)
    tx_count   = card_stats.get("tx_count", 0)
    avg_vel    = card_stats.get("avg_velocity", 0)

    personas = []

    # ── Card Testing ──
    # Small amounts to validate card before big purchase
    card_test_score = 0
    if amount < 5:     card_test_score += 3
    elif amount < 50:  card_test_score += 1
    if velocity >= 5:  card_test_score += 2
    if card_age < 3:   card_test_score += 2
    if tx_count > 0 and avg_amount < 10: card_test_score += 2
    if card_test_score >= 4:
        personas.append({
            "type":        "CARD_TESTING",
            "label":       "Card Testing Attack",
            "confidence":  min(card_test_score / 8, 1.0),
            "description": "Small transactions used to validate stolen card before high-value purchase",
            "indicators":  ["micro_transaction", "high_velocity", "new_card"],
            "severity":    "HIGH"
        })

    # ── Account Takeover ──
    # Legitimate card, behavioral shift
    ato_score = 0
    if is_new_dev:  ato_score += 3
    if is_vpn:      ato_score += 2
    if is_intl:     ato_score += 2
    if is_late:     ato_score += 1
    if tx_count > 3 and avg_amount > 0:
        amount_deviation = abs(amount - avg_amount) / (avg_amount + 1)
        if amount_deviation > 2: ato_score += 3
    if velocity > avg_vel * 2 and avg_vel > 0: ato_score += 2
    if ato_score >= 5:
        personas.append({
            "type":        "ACCOUNT_TAKEOVER",
            "label":       "Account Takeover Attempt",
            "confidence":  min(ato_score / 10, 1.0),
            "description": "Legitimate card compromised — unusual device, location, and behavioral deviation detected",
            "indicators":  ["new_device", "behavioral_deviation", "location_anomaly"],
            "severity":    "CRITICAL"
        })

    # ── Synthetic Identity ──
    # New card, immediately high value, no history
    synth_score = 0
    if card_age < 6:    synth_score += 2
    if tx_count == 0:   synth_score += 3
    if amount > 2000:   synth_score += 2
    if is_crypto:       synth_score += 2
    if is_intl:         synth_score += 1
    if synth_score >= 5:
        personas.append({
            "type":        "SYNTHETIC_IDENTITY",
            "label":       "Synthetic Identity Fraud",
            "confidence":  min(synth_score / 8, 1.0),
            "description": "Fabricated identity — new card immediately used for high-value transactions with no behavioral history",
            "indicators":  ["no_history", "new_card", "high_value_immediately"],
            "severity":    "HIGH"
        })

    # ── Mule / Laundering ──
    # Unusual merchant, round amounts, international transfers
    mule_score = 0
    if transaction.merchant_category in ["Online transfer", "ATM withdrawal"]: mule_score += 2
    if amount % 100 == 0 and amount >= 500: mule_score += 2
    if is_intl:    mule_score += 2
    if velocity >= 3: mule_score += 1
    if tx_count > 0:
        if card_stats.get("merchant_diversity", 0) <= 1: mule_score += 2
    if mule_score >= 4:
        personas.append({
            "type":        "MULE_ACTIVITY",
            "label":       "Money Mule / Laundering",
            "confidence":  min(mule_score / 8, 1.0),
            "description": "Pattern consistent with money mule activity — round amounts, transfer merchants, international routing",
            "indicators":  ["round_amounts", "transfer_merchant", "international"],
            "severity":    "HIGH"
        })

    # ── Friendly Fraud ──
    # Legit card, low risk, but borderline signals
    if not personas and ensemble["confidence"] > 0.3:
        personas.append({
            "type":        "FRIENDLY_FRAUD",
            "label":       "Potential Friendly Fraud",
            "confidence":  round(ensemble["confidence"] * 0.5, 4),
            "description": "Legitimate cardholder may dispute transaction post-delivery — borderline risk signals",
            "indicators":  ["borderline_risk"],
            "severity":    "LOW"
        })

    # Sort by confidence
    personas.sort(key=lambda x: x["confidence"], reverse=True)

    primary = personas[0] if personas else {
        "type":        "UNKNOWN",
        "label":       "No Fraud Pattern Detected",
        "confidence":  0,
        "description": "Transaction appears legitimate with no recognizable fraud signatures",
        "indicators":  [],
        "severity":    "NONE"
    }

    return {
        "primary_persona":  primary,
        "all_personas":     personas,
        "persona_count":    len(personas)
    }

def orchestrate_risk(ensemble: dict, lstm: dict, ae: dict, rules: dict) -> dict:
    W_ENSEMBLE    = 0.35
    W_LSTM        = 0.25
    W_AUTOENCODER = 0.20
    W_RULES       = 0.20

    ensemble_score = ensemble["confidence"]
    lstm_score     = lstm["confidence"]
    ae_score       = min(ae["anomaly_score"], 1.0)
    rule_score     = rules["score"]

    weighted_score = (
        W_ENSEMBLE    * ensemble_score +
        W_LSTM        * lstm_score     +
        W_AUTOENCODER * ae_score       +
        W_RULES       * rule_score
    )

    hard_override   = False
    override_reason = None

    if "EXTREME_AMOUNT" in rules["rules_triggered"]:
        hard_override   = True
        override_reason = "EXTREME_AMOUNT_OVERRIDE"
        weighted_score  = max(weighted_score, 0.85)

    if "TRIPLE_THREAT_VPN_LOCATION_DEVICE" in rules["rules_triggered"]:
        hard_override   = True
        override_reason = "TRIPLE_THREAT_OVERRIDE"
        weighted_score  = max(weighted_score, 0.80)

    if "CRYPTO_NEWCARD_INTERNATIONAL" in rules["rules_triggered"]:
        hard_override   = True
        override_reason = "CRYPTO_RISK_OVERRIDE"
        weighted_score  = max(weighted_score, 0.75)

    is_fraud = weighted_score >= 0.45 or ensemble["is_fraud"]

    if weighted_score >= 0.75 or hard_override:
        risk_tier = "HIGH"
    elif weighted_score >= 0.40:
        risk_tier = "MEDIUM"
    else:
        risk_tier = "LOW"

    return {
        "weighted_score":  round(weighted_score, 4),
        "is_fraud":        is_fraud,
        "risk_tier":       risk_tier,
        "hard_override":   hard_override,
        "override_reason": override_reason,
        "weights": {
            "ensemble":    W_ENSEMBLE,
            "lstm":        W_LSTM,
            "autoencoder": W_AUTOENCODER,
            "rules":       W_RULES
        },
        "component_scores": {
            "ensemble":    round(ensemble_score, 4),
            "lstm":        round(lstm_score, 4),
            "autoencoder": round(ae_score, 4),
            "rules":       round(rule_score, 4)
        }
    }


def generate_llm_explanation(
    transaction: TransactionInput,
    ensemble: dict,
    lstm: dict,
    ae: dict,
    rules: dict,
    card_stats: dict = None,
    persona: dict = None
) -> str:
    try:
        stats_section = ""
        if card_stats and card_stats.get("tx_count", 0) > 0:
            stats_section = f"""
Card Behavioral Profile ({card_stats.get('tx_count', 0)} transactions on record):
- Average amount: ${card_stats.get('avg_amount', 'unknown')}
- Amount std dev: ${card_stats.get('std_amount', 'unknown')}
- Merchant diversity: {card_stats.get('merchant_diversity', 'unknown')} unique merchants
- Location diversity: {card_stats.get('location_diversity', 'unknown')} unique locations
- Average velocity: {card_stats.get('avg_velocity', 'unknown')} tx/24h historically
"""
        else:
            stats_section = "\nCard Behavioral Profile: No prior history on record (new card or first transaction)\n"

        prompt = f"""You are a senior fraud analyst at a major bank. Analyze this transaction and write a professional fraud analysis report.

Transaction Details:
- Amount: ${transaction.amount}
- Merchant: {transaction.merchant_category}
- Location: {transaction.location}
- Time: {transaction.time_of_day}
- Transactions in last 24h: {transaction.transactions_last_24h}
- Card age: {transaction.card_age_months} months
- Device/IP: {transaction.device_match}

ML Ensemble Results (5 models):
- Verdict: {"FRAUD" if ensemble["is_fraud"] else "LEGITIMATE"}
- Ensemble confidence: {round(ensemble["confidence"] * 100, 1)}%
- Model votes: {ensemble["votes"]}/5 flagged as fraud
- XGBoost: {"FRAUD" if ensemble["model_results"]["xgboost"]["fraud"] else "LEGIT"} ({round((ensemble["model_results"]["xgboost"]["confidence"] or 0) * 100, 1)}%)
- Random Forest: {"FRAUD" if ensemble["model_results"]["random_forest"]["fraud"] else "LEGIT"} ({round((ensemble["model_results"]["random_forest"]["confidence"] or 0) * 100, 1)}%)
- Logistic Regression: {"FRAUD" if ensemble["model_results"]["logistic_regression"]["fraud"] else "LEGIT"} ({round((ensemble["model_results"]["logistic_regression"]["confidence"] or 0) * 100, 1)}%)
- Gradient Boosting: {"FRAUD" if ensemble["model_results"]["gradient_boosting"]["fraud"] else "LEGIT"} ({round((ensemble["model_results"]["gradient_boosting"]["confidence"] or 0) * 100, 1)}%)
- Isolation Forest: {"ANOMALY" if ensemble["model_results"]["isolation_forest"]["fraud"] else "NORMAL"}

LSTM Sequence Model:
- Verdict: {"FRAUD" if lstm["fraud"] else "LEGITIMATE"}
- Behavioral anomaly score: {round(lstm["confidence"] * 100, 1)}%

Autoencoder:
- Verdict: {"FRAUD" if ae["fraud"] else "LEGITIMATE"}
- Anomaly score: {ae["anomaly_score"]} (>1.0 means highly anomalous)

Rule Engine ({rules["rule_count"]} rules triggered):
{chr(10).join(f"- {r}" for r in rules["rules_triggered"]) if rules["rules_triggered"] else "- No rules triggered"}

Fraud Persona Analysis:
- Primary persona: {persona["primary_persona"]["label"] if persona else "Unknown"}
- Description: {persona["primary_persona"]["description"] if persona else "N/A"}
- Severity: {persona["primary_persona"]["severity"] if persona else "N/A"}
{stats_section}
Write a concise analyst report with:
1. VERDICT (one line)
2. KEY RISK FACTORS (bullet points)
3. MODEL CONSENSUS (mention ensemble, LSTM, Autoencoder, rules, and card history)
4. RECOMMENDATION (one specific action)

Keep it under 200 words. Be direct and professional."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Analysis unavailable: {str(e)}"
    



@app.get("/")
def root():
    return {"status": "FraudShield API v4.0 running", "models": 7}


@app.post("/predict")
def predict(transaction: TransactionInput, db: Session = Depends(get_db)):
    card_id    = hash(transaction.device_match) % 1000
    history    = get_card_history(db, card_id)
    card_stats = get_card_stats(db, card_id)

    ensemble_result = predict_ensemble(transaction)
    lstm_result     = predict_lstm(transaction, history)
    ae_result       = predict_autoencoder(transaction)
    rule_result     = rule_engine(transaction)
    orchestration   = orchestrate_risk(ensemble_result, lstm_result, ae_result, rule_result)
    persona_result  = detect_fraud_persona(transaction, rule_result, ensemble_result, card_stats)

    is_fraud            = orchestration["is_fraud"]
    combined_confidence = orchestration["weighted_score"]
    risk_tier           = orchestration["risk_tier"]

    explanation = generate_llm_explanation(
        transaction, ensemble_result, lstm_result, ae_result, rule_result, card_stats, persona_result
    )

    record = Transaction(
        amount=transaction.amount,
        merchant_category=transaction.merchant_category,
        location=transaction.location,
        time_of_day=transaction.time_of_day,
        transactions_last_24h=transaction.transactions_last_24h,
        card_age_months=transaction.card_age_months,
        device_match=transaction.device_match,
        is_fraud=is_fraud,
        confidence=combined_confidence,
        risk_tier=risk_tier,
        reason=explanation,
        timestamp=datetime.utcnow()
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    encoders = {
        "merchant_enc": hash(transaction.merchant_category) % 8,
        "location_enc": hash(transaction.location) % 4,
        "time_enc":     hash(transaction.time_of_day) % 4,
        "device_enc":   hash(transaction.device_match) % 5,
    }
    save_card_history(db, card_id, transaction, encoders, is_fraud)

    return {
        "transaction_id":   record.id,
        "is_fraud":         is_fraud,
        "confidence":       combined_confidence,
        "risk_tier":        risk_tier,
        "orchestration":    orchestration,
        "rules":            rule_result,
        "persona":          persona_result,
        "card_stats":       card_stats,
        "ensemble": {
            "verdict":       ensemble_result["is_fraud"],
            "confidence":    ensemble_result["confidence"],
            "votes":         ensemble_result["votes"],
            "model_results": ensemble_result["model_results"]
        },
        "shap":    ensemble_result["shap"],
        "lstm": {
            "verdict":           lstm_result["fraud"],
            "confidence":        lstm_result["confidence"],
            "attention_weights": lstm_result["attention_weights"]
        },
        "autoencoder": {
            "verdict":              ae_result["fraud"],
            "reconstruction_error": ae_result["reconstruction_error"],
            "anomaly_score":        ae_result["anomaly_score"],
            "threshold":            ae_result["threshold"]
        },
        "explanation":    explanation,
        "timestamp":      record.timestamp
    }


@app.get("/transactions")
def get_transactions(db: Session = Depends(get_db)):
    return db.query(Transaction).order_by(
        Transaction.timestamp.desc()
    ).limit(100).all()


@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Transaction).count()
    fraud = db.query(Transaction).filter(Transaction.is_fraud == True).count()
    legit = total - fraud
    return {
        "total":      total,
        "fraud":      fraud,
        "legit":      legit,
        "fraud_rate": round(fraud / total * 100, 2) if total > 0 else 0
    }


@app.get("/metrics")
def get_metrics():
    with open(Path(__file__).parent.parent / "artifacts" / "model_metrics.json") as f:
        metrics = json.load(f)
    metrics["lstm"] = {
        "precision": 0.94,
        "recall":    0.91,
        "f1":        0.925,
        "auc":       0.9458
    }
    metrics["autoencoder"] = {
        "precision": None,
        "recall":    None,
        "f1":        None,
        "auc":       0.9489
    }
    return metrics