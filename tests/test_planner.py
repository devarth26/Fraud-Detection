import pytest

from agent.planner import (
    INTENT_TOOLS,
    choose_tools,
    classify_intent,
    enforce_dependencies,
    extract_transaction_id,
    heuristic_intent,
)

from .fakes import FakeLLM


@pytest.mark.parametrize("text,expected", [
    ("Why was transaction 4812 flagged?", 4812),
    ("look at txn #77", 77),
    ("check #905 please", 905),
    ("ID: 12 looks odd", 12),
    ("card was used 24 times in the last 24h", None),
    ("why was this flagged", None),
])
def test_extract_transaction_id(text, expected):
    assert extract_transaction_id(text) == expected


@pytest.mark.parametrize("query,has_tx,intent", [
    ("Why was this transaction flagged, and what should I do?", True, "full_investigation"),
    ("Why was this flagged?", True, "explain_flag"),
    ("What should I do with this one?", True, "recommend_action"),
    ("Show me this card's spending history", True, "history_check"),
    ("What is our policy on temporary holds?", False, "policy_question"),
    ("What should I do when a card shows micro-transactions?", False, "policy_question"),
    ("Look at this", True, "full_investigation"),
])
def test_heuristic_intent(query, has_tx, intent):
    assert heuristic_intent(query, has_tx) == intent


def test_llm_intent_used_when_valid():
    llm = FakeLLM(lambda p: '{"intent": "history_check"}')
    assert classify_intent(llm, "anything", True) == ("history_check", "llm")


@pytest.mark.parametrize("bad", ["I think it is explain_flag", '{"intent": "make_coffee"}', "{not json"])
def test_llm_garbage_falls_back_to_heuristic(bad):
    llm = FakeLLM(lambda p: bad)
    intent, source = classify_intent(llm, "Why was this flagged?", True)
    assert (intent, source) == ("explain_flag", "heuristic")


def test_llm_tool_choice_is_filtered_to_known_tools():
    llm = FakeLLM(lambda p: '{"tools": ["search_policy", "delete_database", "score_transaction"]}')
    tools, source = choose_tools(llm, "q", "recommend_action")
    assert tools == ["score_transaction", "search_policy"] and source == "llm"


def test_empty_llm_tool_choice_falls_back_to_intent_mapping():
    llm = FakeLLM(lambda p: '{"tools": []}')
    assert choose_tools(llm, "q", "explain_flag") == (INTENT_TOOLS["explain_flag"], "heuristic")


def test_no_llm_uses_intent_mapping():
    assert choose_tools(None, "q", "policy_question") == (["search_policy"], "heuristic")


def test_dependencies_shap_pulls_in_score_and_lookup_added_for_ids():
    tools, needs = enforce_dependencies(["explain_shap"], has_inline_transaction=False, transaction_id=9)
    assert tools == ["lookup_transaction", "score_transaction", "explain_shap"] and needs is None


def test_dependencies_missing_transaction_asks_for_input():
    tools, needs = enforce_dependencies(["score_transaction"], False, None)
    assert tools == [] and "transaction" in needs.lower()


def test_dependencies_inline_transaction_needs_no_lookup():
    tools, _ = enforce_dependencies(["score_transaction", "search_policy"], True, None)
    assert tools == ["score_transaction", "search_policy"]


@pytest.mark.parametrize("query,intent", [
    ("How has this card behaved before? Any past transactions?", "history_check"),
    ("Why did the model score this transaction the way it did?", "explain_flag"),
])
def test_keywords_do_not_match_inside_other_words(query, intent):
    # "action" is inside "transaction"; it must not be read as a request for next steps
    assert heuristic_intent(query, True) == intent


def test_floor_adds_tools_the_planner_left_out_and_reports_them():
    from agent.planner import apply_required_tools

    tools, added = apply_required_tools(["score_transaction", "search_policy"], "full_investigation")
    assert tools == ["score_transaction", "explain_shap", "get_card_history", "search_policy"]
    assert added == ["explain_shap", "get_card_history"]


def test_floor_keeps_optional_extras_and_never_removes_anything():
    from agent.planner import apply_required_tools

    tools, added = apply_required_tools(["score_transaction", "explain_shap", "get_card_history", "search_policy"], "full_investigation")
    assert tools == ["score_transaction", "explain_shap", "get_card_history", "search_policy"] and added == []
    assert apply_required_tools(["get_card_history"], "history_check") == (["get_card_history"], [])


def test_planning_prompt_includes_the_default_plan_for_the_intent():
    llm = FakeLLM(lambda p: '{"tools": ["score_transaction"]}')
    choose_tools(llm, "why flagged?", "explain_flag")
    assert "Default plan for this intent: ['score_transaction', 'explain_shap']" in llm.prompts[0]
