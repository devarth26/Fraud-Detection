"""HTTP endpoints for the scoring service and the investigation agent."""
from __future__ import annotations

import os
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from .database import get_db
from .schemas import TransactionInput
from .scoring import score_transaction

router = APIRouter()

_service = None


def get_service():
    """Built lazily so importing the API never loads embeddings or contacts the LLM."""
    global _service
    if _service is None:
        from agent.service import InvestigationService

        _service = InvestigationService.create()
    return _service


class InvestigateRequest(BaseModel):
    query: str = Field(min_length=3, examples=["Why was transaction 42 flagged, and what should I do?"])
    transaction_id: Optional[int] = None
    transaction: Optional[TransactionInput] = None

    @model_validator(mode="after")
    def _one_source(self):
        if self.transaction is not None and self.transaction_id is not None:
            raise ValueError("Provide either transaction_id or transaction, not both.")
        return self


class ReviewRequest(BaseModel):
    decision: Literal["approve", "escalate", "dismiss"]
    note: str = Field(default="", max_length=2000)


@router.post("/score", tags=["scoring"])
def score(transaction: TransactionInput, db: Session = Depends(get_db)):
    """Score a transaction with all FraudShield models. Read-only: nothing is stored."""
    return score_transaction(transaction, db)


@router.post("/agent/investigate", tags=["agent"])
def investigate(req: InvestigateRequest, service=Depends(get_service)):
    """Ask the investigation agent a question. High-risk cases return status=pending_review."""
    tx = req.transaction.model_dump() if req.transaction else None
    return service.investigate(req.query, transaction_id=req.transaction_id, transaction=tx)


@router.post("/agent/review/{thread_id}", tags=["agent"])
def review(thread_id: str, req: ReviewRequest, service=Depends(get_service)):
    """Record the analyst's decision for a paused high-risk investigation and finish it."""
    try:
        return service.review(thread_id, req.decision, req.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/agent/cases", tags=["agent"])
def cases(limit: int = 50):
    from agent.cases import list_cases

    return list_cases(limit=min(max(limit, 1), 200))


@router.get("/agent/health", tags=["agent"])
def agent_health():
    return {
        "llm_provider": os.getenv("LLM_PROVIDER", "groq"),
        "llm_configured": bool(os.getenv("GROQ_API_KEY")) or os.getenv("LLM_PROVIDER", "groq") == "bedrock",
        "embeddings_provider": os.getenv("EMBEDDINGS_PROVIDER", "huggingface"),
    }
