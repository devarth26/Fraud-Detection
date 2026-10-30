import pytest

from agent.graph import build_graph
from agent.service import InvestigationService

from .fakes import CARD_TEST_TX, HIGH_TX, LOW_TX, FakeBackends, FakeLLM, fake_score


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
        return '{"assessment": "Card testing pattern.", "applicable_policies": [{"id": "POL-001", "why": "micro-transaction burst"}]}'
    svc, _ = make_service(llm=FakeLLM(script))
    r = svc.investigate("anything", transaction=CARD_TEST_TX)
    assert (r["intent_source"], r["plan_source"], r["narrative_source"], r["selection_source"]) == ("llm", "llm", "llm", "llm")
    assert r["tools_used"] == ["score_transaction", "search_policy"]
    assert r["policies_cited"] == ["POL-001"]
    assert "micro-transaction burst" in r["report"]


def test_hallucinated_policy_ids_are_stripped_and_not_counted():
    def script(prompt):
        if "route questions" in prompt:
            return '{"intent": "recommend_action"}'
        if "plan tool calls" in prompt:
            return '{"tools": ["score_transaction", "search_policy"]}'
        return ('{"assessment": "Hold the card per [POL-001] and file under [POL-999].", '
                '"applicable_policies": [{"id": "POL-001", "why": "x"}, {"id": "POL-999", "why": "invented"}]}')
    svc, _ = make_service(llm=FakeLLM(script))
    r = svc.investigate("what should I do", transaction=CARD_TEST_TX)
    assert "POL-999" not in r["report"]
    assert "unverified reference removed" in r["report"]
    assert r["policies_cited"] == ["POL-001"]
    assert any("dropped unverified policy ids" in t for t in r["trace"])
    assert any("removed unverified references" in t for t in r["trace"])


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


def _numpy_score(tx):
    import numpy as np

    s = fake_score(tx)
    s["weighted_score"] = np.float64(s["weighted_score"])
    s["is_fraud"] = np.bool_(s["is_fraud"])
    s["orchestration"]["component_scores"] = {k: np.float32(v) for k, v in s["orchestration"]["component_scores"].items()}
    s["ensemble"]["votes"] = np.int64(s["ensemble"]["votes"])
    s["shap"]["top_features"][0]["shap_value"] = np.float64(0.41)
    s["lstm"]["attention_weights"] = np.array([0.1, 0.2])
    return s


def test_numpy_typed_model_output_survives_checkpointing():
    # Real models return numpy scalars; LangGraph's msgpack checkpointer rejects them unless converted.
    svc, _ = make_service(backends=FakeBackends(score_fn=_numpy_score))
    r = svc.investigate("Why was this flagged and what should I do?", transaction=HIGH_TX)
    assert r["status"] == "pending_review"
    assert isinstance(r["weighted_score"], float)
    done = svc.review(r["thread_id"], "approve", "ok")
    assert done["status"] == "reviewed"


def test_llm_plan_missing_a_required_tool_is_corrected_and_recorded():
    def script(prompt):
        if "route questions" in prompt:
            return '{"intent": "full_investigation"}'
        if "plan tool calls" in prompt:
            return '{"tools": ["score_transaction", "search_policy"]}'  # forgets explain_shap
        return "Assessment: ok. 1. Hold the card per [POL-001]."
    svc, _ = make_service(llm=FakeLLM(script))
    r = svc.investigate("Why was this flagged and what should I do?", transaction=CARD_TEST_TX)
    assert r["plan_source"] == "llm" and r["plan_added"] == ["explain_shap", "get_card_history"]
    assert "explain_shap" in r["tools_used"]
    assert "SHAP drivers" in r["report"]
    assert any("required tools added" in t for t in r["trace"])


def test_assessment_prompt_carries_the_faithfulness_rules_and_the_driver_finding():
    prompts = []

    def script(prompt):
        prompts.append(prompt)
        if "route questions" in prompt:
            return '{"intent": "recommend_action"}'
        if "plan tool calls" in prompt:
            return '{"tools": ["score_transaction", "search_policy"]}'
        return "ok [POL-001]"
    svc, _ = make_service(llm=FakeLLM(script))
    svc.investigate("what should I do", transaction=CARD_TEST_TX)
    narrative_prompt = prompts[-1]
    assert "What drove the rating" in narrative_prompt
    assert "Never describe a model that scored low" in narrative_prompt
    assert "do not raise or lower the final rating" in narrative_prompt
    assert "Leave out the rest" in narrative_prompt


def llm_script(selection, assessment="Assessment text."):
    import json

    def script(prompt):
        if "route questions" in prompt:
            return '{"intent": "recommend_action"}'
        if "plan tool calls" in prompt:
            return '{"tools": ["score_transaction", "search_policy"]}'
        return json.dumps({"assessment": assessment, "applicable_policies": selection})
    return script


def test_actions_are_copied_verbatim_from_the_policies_the_llm_selected():
    sel = [{"id": "POL-005", "why": "amount above 50,000"}, {"id": "POL-004", "why": "international transfer"}]
    svc, _ = make_service(llm=FakeLLM(llm_script(sel)))
    r = svc.investigate("what should I do", transaction=HIGH_TX)
    assert "obtain two independent analyst approvals" in r["report"]  # POL-005 step, never written by the LLM
    assert "Do not tip off the customer" in r["report"]                # POL-004 step
    assert sorted(r["policies_cited"]) == ["POL-004", "POL-005"]
    assert "amount above 50,000" in r["report"]


def test_policies_the_llm_leaves_out_get_no_steps():
    svc, _ = make_service(llm=FakeLLM(llm_script([{"id": "POL-005", "why": "large amount"}])))
    r = svc.investigate("what should I do", transaction=HIGH_TX)
    assert r["policies_cited"] == ["POL-005"]
    assert "Do not tip off the customer" not in r["report"]


def test_empty_llm_selection_on_a_flagged_case_falls_back_to_signals():
    svc, _ = make_service(llm=FakeLLM(llm_script([])))
    r = svc.investigate("what should I do", transaction=CARD_TEST_TX)
    assert r["selection_source"] == "signals" and "POL-001" in r["policies_cited"]
    assert any("used rule/persona signals" in t for t in r["trace"])


def test_non_json_assessment_falls_back_to_the_template_but_keeps_the_plan_source():
    def script(prompt):
        if "route questions" in prompt:
            return '{"intent": "recommend_action"}'
        if "plan tool calls" in prompt:
            return '{"tools": ["score_transaction", "search_policy"]}'
        return "Sure! Here is my analysis in plain text."
    svc, _ = make_service(llm=FakeLLM(script))
    r = svc.investigate("what should I do", transaction=CARD_TEST_TX)
    assert (r["plan_source"], r["narrative_source"], r["selection_source"]) == ("llm", "template", "signals")


def test_template_path_renders_the_policy_steps_too():
    svc, _ = make_service()
    r = svc.investigate("Why was this flagged and what should I do?", transaction=CARD_TEST_TX)
    assert "## Recommended actions" in r["report"]
    assert "Place a temporary hold on the card" in r["report"]  # POL-001 step 1


def test_extra_tools_the_llm_adds_to_a_history_question_are_removed_and_recorded():
    def script(prompt):
        if "route questions" in prompt:
            return '{"intent": "history_check"}'
        if "plan tool calls" in prompt:
            return '{"tools": ["get_card_history", "score_transaction", "search_policy"]}'
        return "{}"
    svc, fb = make_service(llm=FakeLLM(script))
    r = svc.investigate("Show me this card's spending history", transaction=LOW_TX)
    assert r["tools_used"] == ["get_card_history"] and fb.score_calls == 0
    assert r["plan_removed"] == ["score_transaction", "search_policy"]
    assert any("extra tools removed" in t for t in r["trace"])


# ---------------------------------------------------------------- persona labels and retrieval
def _spy_service(score_fn):
    fb = FakeBackends(score_fn=score_fn)
    backends = fb.build()
    calls = []
    original = backends.search_policy

    def spy(q, k=4, rule_codes=None, personas=None):
        calls.append({"query": q, "rules": rule_codes, "personas": personas})
        return original(q, k=k, rule_codes=rule_codes, personas=personas)

    backends.search_policy = spy
    return InvestigationService(build_graph(backends=backends, llm=None)), calls


def _synthetic_label(tx):
    from .fakes import make_score

    return make_score("MEDIUM", 0.5, ["HIGH_AMOUNT"], "SYNTHETIC_IDENTITY", "Synthetic Identity Fraud")


def _takeover_label(tx):
    from .fakes import make_score

    return make_score("MEDIUM", 0.5, ["HIGH_AMOUNT"], "ACCOUNT_TAKEOVER", "Account Takeover")


def test_a_contradicted_persona_does_not_steer_retrieval_by_default():
    svc, calls = _spy_service(_synthetic_label)
    r = svc.investigate("Why was this flagged and what should I do?", transaction=LOW_TX)  # card is 30 months old
    assert calls[0]["personas"] == [] and "Synthetic Identity" not in calls[0]["query"]
    assert "POL-003" not in r["policies_cited"]


def test_a_persona_the_data_supports_still_steers_retrieval():
    svc, calls = _spy_service(_synthetic_label)
    svc.investigate("Why was this flagged and what should I do?", transaction=CARD_TEST_TX)  # card is 1 month old
    assert calls[0]["personas"] == ["SYNTHETIC_IDENTITY"]
    svc, calls = _spy_service(_takeover_label)
    svc.investigate("Why was this flagged and what should I do?", transaction=LOW_TX)  # takeover is never gated
    assert calls[0]["personas"] == ["ACCOUNT_TAKEOVER"] and "Account Takeover" in calls[0]["query"]


def test_persona_mode_all_restores_the_old_behaviour_and_off_removes_it(monkeypatch):
    import agent.nodes

    monkeypatch.setattr(agent.nodes, "PERSONA_MODE", "all")
    svc, calls = _spy_service(_synthetic_label)
    r = svc.investigate("Why was this flagged and what should I do?", transaction=LOW_TX)
    assert calls[0]["personas"] == ["SYNTHETIC_IDENTITY"] and "POL-003" in r["policies_cited"]
    monkeypatch.setattr(agent.nodes, "PERSONA_MODE", "off")
    svc, calls = _spy_service(_takeover_label)
    svc.investigate("Why was this flagged and what should I do?", transaction=LOW_TX)
    assert calls[0]["personas"] == []
