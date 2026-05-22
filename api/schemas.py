from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class TransactionInput(BaseModel):
    amount: float
    merchant_category: str
    location: str
    time_of_day: str
    transactions_last_24h: int
    card_age_months: int
    device_match: str

class PredictionResponse(BaseModel):
    transaction_id: int
    is_fraud: bool
    confidence: float
    risk_tier: str
    reason: str
    timestamp: datetime

class StatsResponse(BaseModel):
    total: int
    fraud: int
    legit: int
    fraud_rate: float