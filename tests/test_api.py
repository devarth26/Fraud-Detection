import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.graph import build_graph
from agent.service import InvestigationService
from api.agent_routes import get_service, router

from .fakes import HIGH_TX, LOW_TX, FakeBackends


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    service = InvestigationService(build_graph(backends=FakeBackends().build(), llm=None))
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


def test_investigate_low_risk_completes(client):
    r = client.post("/agent/investigate", json={"query": "Why was this flagged and what should I do?", "transaction": LOW_TX})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed" and body["report"].startswith("# Investigation report")


def test_high_risk_requires_review_then_resumes(client):
    r = client.post("/agent/investigate", json={"query": "Why was this flagged and what should I do?", "transaction": HIGH_TX})
    body = r.json()
    assert body["status"] == "pending_review"
    done = client.post(f"/agent/review/{body['thread_id']}", json={"decision": "escalate", "note": "linked accounts"})
    assert done.status_code == 200 and done.json()["status"] == "reviewed"
    again = client.post(f"/agent/review/{body['thread_id']}", json={"decision": "approve"})
    assert again.status_code == 409


def test_review_unknown_thread_is_404(client):
    assert client.post("/agent/review/nope", json={"decision": "approve"}).status_code == 404


def test_invalid_decision_and_conflicting_inputs_are_422(client):
    assert client.post("/agent/review/x", json={"decision": "maybe"}).status_code == 422
    both = {"query": "why flagged?", "transaction_id": 1, "transaction": LOW_TX}
    assert client.post("/agent/investigate", json=both).status_code == 422
