import pytest

from agent.graph import build_graph
from agent.service import InvestigationService

from .fakes import CARD_TEST_TX, HIGH_TX, LOW_TX, FakeBackends, FakeLLM


def make_service(llm=None, backends=None):
    fb = backends or FakeBackends()
    return InvestigationService(build_graph(backends=fb.build(), llm=llm)), fb


def test_low_risk_full_investigation_completes_without_review():
    svc, fb = make_service()
    r = svc.investigate("Why was this transaction flagged, and what should I do?", transaction=LOW_TX)
    assert r["status"] == "completed"
    assert r["intent"] == "full_investigation"
    assert r["tools_used"] == ["score_transaction", "explain_shap", "get_card_history", "search_policy"]
    assert r["review_request"] is None and r["review"] is None
    assert r["narrative_source"] == "template"
    assert len(fb.saved_cases) == 1 and r["case_id"] == 1


def test_high_risk_pauses_for_human_review_then_resumes():
    svc, fb = make_service()
    r = svc.investigate("Why was this flagged and what should I do?", transaction=HIGH_TX)
    assert r["status"] == "pending_review"
    assert r["review_request"]["options"] == ["approve", "escalate", "dismiss"]
    assert "Human review required" in r["report"]
    assert fb.saved_cases == []  # nothing is recorded until a human decides

    done = svc.review(r["thread_id"], "approve", "Customer unreachable, blocking card.")
    assert done["status"] == "reviewed"
    assert done["review"] == {"decision": "approve", "note": "Customer unreachable, blocking card."}
    assert "## Analyst review" in done["report"]
    assert fb.saved_cases[0]["review"]["decision"] == "approve"
    assert fb.saved_cases[0]["status"] == "reviewed"


def test_review_cannot_be_submitted_twice_or_for_unknown_thread():
    svc, _ = make_service()
    r = svc.investigate("Why was this flagged and what should I do?", transaction=HIGH_TX)
    svc.review(r["thread_id"], "dismiss", "false positive")
    with pytest.raises(ValueError):
        svc.review(r["thread_id"], "approve", "again")
    with pytest.raises(LookupError):
        svc.review("does-not-exist", "approve", "")


def test_policy_question_needs_no_transaction_and_only_searches_policy():
    svc, fb = make_service()
    r = svc.investigate("What is our policy on temporary holds and how long can they last?")
    assert r["status"] == "completed"
    assert r["intent"] == "policy_question"
    assert r["tools_used"] == ["search_policy"]
    assert "POL-008" in r["policies_retrieved"]
    assert fb.score_calls == 0 and fb.saved_cases == []


def test_missing_transaction_returns_needs_input_and_calls_nothing():
    svc, fb = make_service()
    r = svc.investigate("Why was this flagged?")
    assert r["status"] == "needs_input"
    assert r["tools_used"] == [] and fb.score_calls == 0
    assert "transaction" in r["report"].lower()


def test_transaction_id_triggers_sql_lookup_before_scoring():
    svc, fb = make_service()
    r = svc.investigate("Why was transaction 42 flagged?")
    assert r["tools_used"][:2] == ["lookup_transaction", "score_transaction"]
    assert r["status"] == "completed"
    assert fb.saved_cases[0]["transaction_id"] == 42


def test_unknown_transaction_id_is_reported_not_crashed():
    svc, fb = make_service()
    r = svc.investigate("Why was transaction 999 flagged?")
    assert r["status"] == "needs_input" and "not found" in r["report"]
    assert fb.score_calls == 0


def test_card_testing_case_cites_card_testing_policy():
    svc, _ = make_service()
    r = svc.investigate("Why was this flagged and what should I do?", transaction=CARD_TEST_TX)
    assert "POL-001" in r["policies_retrieved"]
    assert "POL-001" in r["policies_cited"]


def test_history_check_runs_only_history_tool():
    svc, fb = make_service()
    r = svc.investigate("Show me this card's spending history", transaction=LOW_TX)
    assert r["tools_used"] == ["get_card_history"] and fb.score_calls == 0


def test_llm_planner_and_narrative_are_used_when_available():
    def script(prompt):
        if "route questions" in prompt:
            return '{"intent": "recommend_action"}'
        if "plan tool calls" in prompt:
            return '{"tools": ["score_transaction", "search_policy"]}'
        return "Assessment: card testing. 1. Place a hold per [POL-001]."
    svc, _ = make_service(llm=FakeLLM(script))
    r = svc.investigate("anything", transaction=CARD_TEST_TX)
    assert (r["intent_source"], r["plan_source"], r["narrative_source"]) == ("llm", "llm", "llm")
    assert r["tools_used"] == ["score_transaction", "search_policy"]
    assert r["policies_cited"] == ["POL-001"]


def test_hallucinated_policy_ids_are_stripped_and_not_counted():
    def script(prompt):
        if "route questions" in prompt:
            return '{"intent": "recommend_action"}'
        if "plan tool calls" in prompt:
            return '{"tools": ["score_transaction", "search_policy"]}'
        return "Hold the card per [POL-001] and file under [POL-999]."
    svc, _ = make_service(llm=FakeLLM(script))
    r = svc.investigate("what should I do", transaction=CARD_TEST_TX)
    assert "POL-999" not in r["report"]
    assert "unverified reference removed" in r["report"]
    assert r["policies_cited"] == ["POL-001"]
    assert any("removed unverified" in t for t in r["trace"])


def test_llm_failure_falls_back_to_template_everywhere():
    class Broken:
        def invoke(self, prompt):
            raise RuntimeError("rate limited")
    svc, _ = make_service(llm=Broken())
    r = svc.investigate("Why was this flagged and what should I do?", transaction=LOW_TX)
    assert (r["intent_source"], r["plan_source"], r["narrative_source"]) == ("heuristic", "heuristic", "template")
    assert r["status"] == "completed"


def test_scoring_failure_degrades_gracefully():
    def boom(tx):
        raise RuntimeError("model artifact missing")
    svc, _ = make_service(backends=FakeBackends(score_fn=boom))
    r = svc.investigate("Why was this flagged and what should I do?", transaction=LOW_TX)
    assert r["status"] == "completed"
    assert r["risk_tier"] is None
    assert any("score_transaction FAILED" in t for t in r["trace"])


def test_invalid_review_decision_defaults_to_escalate():
    svc, _ = make_service()
    r = svc.investigate("Why was this flagged and what should I do?", transaction=HIGH_TX)
    done = svc.review(r["thread_id"], "yolo", "")
    assert done["review"]["decision"] == "escalate"


def test_benign_transaction_gets_no_policy_citations_from_template():
    svc, _ = make_service()
    r = svc.investigate("Why was this flagged and what should I do?", transaction=LOW_TX)
    assert r["policies_cited"] == []
    assert "no policy action is required" in r["report"]
