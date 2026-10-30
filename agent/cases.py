"""Persistence for completed investigations (the analyst audit trail)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from api.database import Base, SessionLocal, engine


class InvestigationCase(Base):
    __tablename__ = "investigation_cases"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    query = Column(Text)
    transaction_id = Column(Integer, nullable=True, index=True)
    intent = Column(String)
    risk_tier = Column(String, nullable=True)
    weighted_score = Column(Float, nullable=True)
    tools_used = Column(String)
    policies_cited = Column(String)
    report = Column(Text)
    status = Column(String)
    analyst_decision = Column(String, nullable=True)
    analyst_note = Column(Text, nullable=True)


_table_ready = False


def ensure_table() -> None:
    # api.database runs create_all() at import time, before this model is defined,
    # so this table is created lazily on first use.
    global _table_ready
    if not _table_ready:
        Base.metadata.create_all(bind=engine, tables=[InvestigationCase.__table__])
        _table_ready = True


def save_case(data: dict) -> int:
    ensure_table()
    with SessionLocal() as db:
        row = InvestigationCase(
            query=data.get("query"),
            transaction_id=data.get("transaction_id"),
            intent=data.get("intent"),
            risk_tier=data.get("risk_tier"),
            weighted_score=data.get("weighted_score"),
            tools_used=",".join(data.get("tools_used", [])),
            policies_cited=",".join(data.get("policies_cited", [])),
            report=data.get("report"),
            status=data.get("status"),
            analyst_decision=(data.get("review") or {}).get("decision"),
            analyst_note=(data.get("review") or {}).get("note"),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def list_cases(limit: int = 50) -> list[dict]:
    ensure_table()
    with SessionLocal() as db:
        rows = db.query(InvestigationCase).order_by(InvestigationCase.created_at.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "transaction_id": r.transaction_id,
                "intent": r.intent,
                "risk_tier": r.risk_tier,
                "weighted_score": r.weighted_score,
                "policies_cited": r.policies_cited.split(",") if r.policies_cited else [],
                "status": r.status,
                "analyst_decision": r.analyst_decision,
                "analyst_note": r.analyst_note,
            }
            for r in rows
        ]
