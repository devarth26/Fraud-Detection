from sqlalchemy import create_engine, Column, Integer, Float, Boolean, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://frauduser:fraudpass123@localhost/fraudshield")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Float)
    merchant_category = Column(String)
    location = Column(String)
    time_of_day = Column(String)
    transactions_last_24h = Column(Integer)
    card_age_months = Column(Integer)
    device_match = Column(String)
    is_fraud = Column(Boolean)
    confidence = Column(Float)
    risk_tier = Column(String)
    reason = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Base.metadata.create_all(bind=engine)

class CardProfile(Base):
    __tablename__ = "card_profiles"

    id             = Column(Integer, primary_key=True, index=True)
    card_id        = Column(Integer, index=True)
    amount         = Column(Float)
    merchant_enc   = Column(Integer)
    location_enc   = Column(Integer)
    time_enc       = Column(Integer)
    device_enc     = Column(Integer)
    transactions_last_24h = Column(Integer)
    card_age_months = Column(Integer)
    timestamp      = Column(DateTime, default=datetime.utcnow)
    is_fraud       = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_card_history(db, card_id: int, limit: int = 10) -> list:
    records = db.query(CardProfile).filter(
        CardProfile.card_id == card_id
    ).order_by(CardProfile.timestamp.desc()).limit(limit).all()
    
    history = []
    for r in reversed(records):
        history.append({
            "amount":                r.amount,
            "merchant_enc":          r.merchant_enc,
            "location_enc":          r.location_enc,
            "time_enc":              r.time_enc,
            "device_enc":            r.device_enc,
            "transactions_last_24h": r.transactions_last_24h,
            "card_age_months":       r.card_age_months,
        })
    return history


def save_card_history(db, card_id: int, transaction, encoders: dict, is_fraud: bool):
    record = CardProfile(
        card_id               = card_id,
        amount                = transaction.amount,
        merchant_enc          = encoders["merchant_enc"],
        location_enc          = encoders["location_enc"],
        time_enc              = encoders["time_enc"],
        device_enc            = encoders["device_enc"],
        transactions_last_24h = transaction.transactions_last_24h,
        card_age_months       = transaction.card_age_months,
        is_fraud              = is_fraud,
        timestamp             = datetime.utcnow()
    )
    db.add(record)
    db.commit()


def get_card_stats(db, card_id: int) -> dict:
    from sqlalchemy import func
    records = db.query(CardProfile).filter(
        CardProfile.card_id == card_id
    ).order_by(CardProfile.timestamp.desc()).limit(50).all()

    if not records:
        return {
            "tx_count":           0,
            "avg_amount":         0,
            "std_amount":         0,
            "dominant_merchant":  0,
            "dominant_location":  0,
            "merchant_diversity": 0,
            "location_diversity": 0,
            "avg_velocity":       0
        }

    amounts   = [r.amount for r in records]
    merchants = [r.merchant_enc for r in records]
    locations = [r.location_enc for r in records]

    import numpy as np
    return {
        "tx_count":           len(records),
        "avg_amount":         round(float(np.mean(amounts)), 2),
        "std_amount":         round(float(np.std(amounts)), 2),
        "dominant_merchant":  max(set(merchants), key=merchants.count),
        "dominant_location":  max(set(locations), key=locations.count),
        "merchant_diversity": len(set(merchants)),
        "location_diversity": len(set(locations)),
        "avg_velocity":       round(float(np.mean([r.transactions_last_24h for r in records])), 2)
    }