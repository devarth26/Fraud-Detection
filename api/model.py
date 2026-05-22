import joblib
import numpy as np
import json
import torch
import torch.nn as nn
from pathlib import Path

ARTIFACTS = Path(__file__).parent.parent / "artifacts"

# ── Ensemble models ──
xgb_model = joblib.load(ARTIFACTS / "xgb_v2.pkl")
rf_model  = joblib.load(ARTIFACTS / "rf_v2.pkl")
lr_model  = joblib.load(ARTIFACTS / "lr_v2.pkl")
gb_model  = joblib.load(ARTIFACTS / "gb_v2.pkl")
iso_model = joblib.load(ARTIFACTS / "iso_v2.pkl")

# ── Encoders ──
le_merchant = joblib.load(ARTIFACTS / "le_merchant.pkl")
le_location = joblib.load(ARTIFACTS / "le_location.pkl")
le_time     = joblib.load(ARTIFACTS / "le_time.pkl")
le_device   = joblib.load(ARTIFACTS / "le_device.pkl")
scaler      = joblib.load(ARTIFACTS / "scaler.pkl")

with open(ARTIFACTS / "feature_cols.json") as f:
    feature_cols = json.load(f)

# ── LSTM Architecture (must match notebook exactly) ──
class AttentionLayer(nn.Module):
    def __init__(self, hidden_size):
        super().__init__()
        self.attention = nn.Linear(hidden_size * 2, 1)

    def forward(self, lstm_output):
        attention_weights = torch.softmax(self.attention(lstm_output), dim=1)
        context = (attention_weights * lstm_output).sum(dim=1)
        return context, attention_weights.squeeze(-1)

class FraudLSTM(nn.Module):
    def __init__(self, input_size, hidden_size=128, num_layers=2, dropout=0.3):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size, hidden_size=hidden_size,
            num_layers=num_layers, batch_first=True,
            dropout=dropout, bidirectional=True
        )
        self.attention  = AttentionLayer(hidden_size)
        self.batch_norm = nn.BatchNorm1d(hidden_size * 2)
        self.classifier = nn.Sequential(
            nn.Linear(hidden_size * 2, 64), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(64, 32), nn.ReLU(), nn.Dropout(dropout * 0.5),
            nn.Linear(32, 1), nn.Sigmoid()
        )

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        context, attn_weights = self.attention(lstm_out)
        context = self.batch_norm(context)
        output  = self.classifier(context)
        return output.squeeze(-1), attn_weights

# ── Load LSTM lazily ──
_lstm_model = None
_lstm_threshold = None
_lstm_input_size = None

def get_lstm():
    global _lstm_model, _lstm_threshold, _lstm_input_size
    if _lstm_model is None:
        checkpoint = torch.load(
            ARTIFACTS / "lstm_model.pt",
            map_location=torch.device('cpu'),
            weights_only=False
        )
        _lstm_input_size = checkpoint['input_size']
        _lstm_threshold  = checkpoint['optimal_threshold']
        m = FraudLSTM(
            input_size=checkpoint['input_size'],
            hidden_size=checkpoint['hidden_size'],
            num_layers=checkpoint['num_layers']
        )
        m.load_state_dict(checkpoint['model_state_dict'])
        m.eval()
        _lstm_model = m
    return _lstm_model, _lstm_threshold, _lstm_input_size

# ── Autoencoder ──
_ae_model = None
_ae_threshold = None
_ae_scaler = None

class FraudAutoencoder(nn.Module):
    def __init__(self, input_dim):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 64), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(32, 16), nn.ReLU(),
            nn.Linear(16, 8)
        )
        self.decoder = nn.Sequential(
            nn.Linear(8, 16), nn.ReLU(),
            nn.Linear(16, 32), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(32, 64), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(64, input_dim)
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))

    def reconstruction_error(self, x):
        with torch.no_grad():
            reconstructed = self.forward(x)
            error = torch.mean((x - reconstructed) ** 2, dim=1)
        return error

def get_autoencoder():
    global _ae_model, _ae_threshold, _ae_scaler
    if _ae_model is None:
        checkpoint = torch.load(
            ARTIFACTS / "autoencoder_model.pt",
            map_location=torch.device('cpu'),
            weights_only=False
        )
        m = FraudAutoencoder(input_dim=checkpoint['input_dim'])
        m.load_state_dict(checkpoint['model_state_dict'])
        m.eval()
        _ae_model     = m
        _ae_threshold = checkpoint['optimal_threshold']
        _ae_scaler    = joblib.load(ARTIFACTS / "ae_scaler.pkl")
    return _ae_model, _ae_threshold, _ae_scaler

# ── SHAP Explainer ──
_shap_explainer = None

def get_shap_explainer():
    global _shap_explainer
    if _shap_explainer is None:
        import shap
        _shap_explainer = joblib.load(ARTIFACTS / "shap_explainer.pkl")
    return _shap_explainer

def compute_shap(features: list, feature_cols: list) -> dict:
    try:
        import shap
        explainer = get_shap_explainer()
        arr = np.array(features).reshape(1, -1)
        import pandas as pd
        df = pd.DataFrame(arr, columns=feature_cols)
        shap_vals = explainer.shap_values(df)

        contributions = []
        for i, (feat, val) in enumerate(zip(feature_cols, shap_vals[0])):
            contributions.append({
                "feature":      feat,
                "value":        round(float(features[i]), 4),
                "shap_value":   round(float(val), 4),
                "direction":    "fraud" if val > 0 else "legit",
                "abs_impact":   round(abs(float(val)), 4)
            })

        contributions.sort(key=lambda x: x["abs_impact"], reverse=True)

        return {
            "top_features":   contributions[:8],
            "base_value":     round(float(explainer.expected_value), 4),
            "total_shap":     round(float(sum(v["shap_value"] for v in contributions)), 4)
        }
    except Exception as e:
        return {"error": str(e), "top_features": [], "base_value": 0, "total_shap": 0}

def predict_autoencoder(transaction) -> dict:
    ae_model, ae_threshold, ae_scaler = get_autoencoder()
    
    # Get the input dim the autoencoder was trained on
    input_dim = ae_model.encoder[0].in_features
    
    features = encode_transaction(transaction)
    
    # Pad or trim to match autoencoder's expected input size
    if len(features) < input_dim:
        features = features + [0.0] * (input_dim - len(features))
    else:
        features = features[:input_dim]
    
    ae_input = np.array(features, dtype=np.float32).reshape(1, -1)

    # Normalize manually — keep values in reasonable range
    ae_input_scaled = np.clip(ae_input / (np.abs(ae_input).max() + 1e-8), -3, 3)

    tensor = torch.tensor(ae_input_scaled, dtype=torch.float32)
    error  = float(ae_model.reconstruction_error(tensor).item())
    is_fraud = bool(error >= ae_threshold)

    return {
        "fraud":                is_fraud,
        "reconstruction_error": round(error, 6),
        "threshold":            round(ae_threshold, 6),
        "anomaly_score":        round(min(error / ae_threshold, 2.0), 4)
    }

def encode_transaction(t) -> list:
    def safe_encode(encoder, value):
        if value in encoder.classes_:
            return int(encoder.transform([value])[0])
        return 0

    merchant_enc = safe_encode(le_merchant, t.merchant_category)
    location_enc = safe_encode(le_location, t.location)
    time_enc     = safe_encode(le_time,     t.time_of_day)
    device_enc   = safe_encode(le_device,   t.device_match)
    amount_scaled = float(scaler.transform([[t.amount]])[0][0])

    is_high_risk_location = int(t.location in ['High-risk country', 'International'])
    is_late_night         = int(t.time_of_day in ['Late night (12–5am)', 'Early morning'])
    is_vpn                = int(t.device_match == 'VPN / proxy detected')
    is_new_device         = int(t.device_match in ['New device, new IP', 'New device, matching IP'])
    is_high_risk_merchant = int(t.merchant_category in ['Crypto exchange', 'ATM withdrawal', 'Online transfer'])
    is_new_card           = int(t.card_age_months < 6)
    is_high_amount        = int(t.amount > 5000)
    is_micro_transaction  = int(t.amount < 1.0)
    is_high_velocity      = int(t.transactions_last_24h > 5)
    amount_per_card_age   = t.amount / (t.card_age_months + 1)
    velocity_x_amount     = t.transactions_last_24h * t.amount
    risk_score = (
        is_high_risk_location * 3 + is_vpn * 3 + is_late_night * 2 +
        is_new_device * 2 + is_high_risk_merchant * 2 + is_new_card * 2 +
        is_high_amount * 2 + is_high_velocity * 2 + is_micro_transaction * 2
    )

    return [
        amount_scaled, t.transactions_last_24h, t.card_age_months,
        merchant_enc, location_enc, time_enc, device_enc,
        is_high_risk_location, is_late_night, is_vpn, is_new_device,
        is_high_risk_merchant, is_new_card, is_high_amount,
        is_micro_transaction, is_high_velocity,
        amount_per_card_age, velocity_x_amount, risk_score
    ]

def predict_ensemble(transaction) -> dict:
    features = encode_transaction(transaction)
    arr = np.array(features).reshape(1, -1)

    xgb_prob = float(xgb_model.predict_proba(arr)[0][1])
    rf_prob  = float(rf_model.predict_proba(arr)[0][1])
    lr_prob  = float(lr_model.predict_proba(arr)[0][1])
    gb_prob  = float(gb_model.predict_proba(arr)[0][1])
    iso_pred = int(iso_model.predict(arr)[0])

    xgb_fraud = bool(xgb_prob >= 0.5)
    rf_fraud  = bool(rf_prob  >= 0.5)
    lr_fraud  = bool(lr_prob  >= 0.5)
    gb_fraud  = bool(gb_prob  >= 0.5)
    iso_fraud = bool(iso_pred == -1)

    votes = sum([xgb_fraud, rf_fraud, lr_fraud, gb_fraud, iso_fraud])
    ensemble_prob = (xgb_prob + rf_prob + lr_prob + gb_prob) / 4

# Compute SHAP for XGBoost
    shap_result = compute_shap(features, feature_cols)

    return {
        "is_fraud":      bool(votes >= 3),
        "confidence":    round(ensemble_prob, 4),
        "votes":         int(votes),
        "model_results": {
            "xgboost":             {"fraud": xgb_fraud, "confidence": round(xgb_prob, 4)},
            "random_forest":       {"fraud": rf_fraud,  "confidence": round(rf_prob,  4)},
            "logistic_regression": {"fraud": lr_fraud,  "confidence": round(lr_prob,  4)},
            "gradient_boosting":   {"fraud": gb_fraud,  "confidence": round(gb_prob,  4)},
            "isolation_forest":    {"fraud": iso_fraud, "confidence": None}
        },
        "shap": shap_result
    }

def predict_lstm(transaction, card_history: list) -> dict:
    """
    card_history: list of last 10 transactions for this card
    Each item is a dict with the same fields as TransactionInput
    """
    SEQUENCE_LENGTH = 10

    def tx_to_lstm_features(tx_dict):
        amount        = tx_dict.get('amount', 0)
        amount_scaled = float(scaler.transform([[amount]])[0][0])
        merchant_enc  = tx_dict.get('merchant_enc', 0)
        location_enc  = tx_dict.get('location_enc', 0)
        time_enc      = tx_dict.get('time_enc', 0)
        device_enc    = tx_dict.get('device_enc', 0)
        tx_24h        = tx_dict.get('transactions_last_24h', 0)
        card_age      = tx_dict.get('card_age_months', 12)
        return [
            amount_scaled, tx_24h, card_age,
            merchant_enc, location_enc, time_enc, device_enc,
            0, 0, 0, 0, 0
        ]

    # Build sequence from history + current transaction
    current_features = encode_transaction(transaction)
    lstm_current = [
        current_features[0],  # amount_scaled
        current_features[1],  # transactions_last_24h
        current_features[2],  # card_age_months
        current_features[3],  # merchant_enc
        current_features[4],  # location_enc
        current_features[5],  # time_enc
        current_features[6],  # device_enc
        current_features[7],  # is_high_risk_location
        current_features[8],  # is_late_night
        current_features[9],  # is_vpn
        current_features[10], # is_new_device
        current_features[11], # is_high_risk_merchant
    ]

    # Pad history if needed
    seq = [tx_to_lstm_features(h) for h in card_history[-SEQUENCE_LENGTH+1:]]
    while len(seq) < SEQUENCE_LENGTH - 1:
        seq.insert(0, [0.0] * 12)
    seq.append(lstm_current)

    # Run LSTM
    lstm_model, LSTM_THRESHOLD, _ = get_lstm()
    tensor = torch.tensor([seq], dtype=torch.float32)
    with torch.no_grad():
        prob, attn_weights = lstm_model(tensor)

    lstm_prob  = float(prob.item())
    lstm_fraud = bool(lstm_prob >= LSTM_THRESHOLD)
    attn_list  = attn_weights[0].numpy().tolist()

    return {
        "fraud":             lstm_fraud,
        "confidence":        round(lstm_prob, 4),
        "attention_weights": [round(w, 4) for w in attn_list]
    }