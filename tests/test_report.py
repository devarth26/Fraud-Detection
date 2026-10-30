import pytest

from agent.report import build_facts, driver_line

from .fakes import make_score


def score_with(models, rules, override=None):
    s = make_score("HIGH", 0.85, ["EXTREME_AMOUNT"])
    s["orchestration"]["component_scores"] = {"ensemble": models[0], "lstm": models[1], "autoencoder": models[2], "rules": rules}
    s["orchestration"]["hard_override"] = bool(override)
    s["orchestration"]["override_reason"] = override
    return s


def test_hard_override_with_low_models_says_the_models_did_not_flag_it():
    # the real case from the first live run: rule override drove HIGH while all three models scored low
    line = driver_line(score_with((0.09, 0.13, 0.06), 1.0, "EXTREME_AMOUNT_OVERRIDE"))
    assert "EXTREME_AMOUNT_OVERRIDE hard override" in line
    assert "did NOT flag it" in line and "ensemble 0.09" in line


def test_hard_override_with_high_models_says_they_agree():
    line = driver_line(score_with((0.9, 0.8, 0.7), 1.0, "EXTREME_AMOUNT_OVERRIDE"))
    assert "also scored high" in line


@pytest.mark.parametrize("models,rules,expected", [
    ((0.1, 0.1, 0.1), 0.9, "the rule engine"),
    ((0.9, 0.2, 0.1), 0.1, "the learned models"),
    ((0.9, 0.8, 0.7), 0.9, "agree"),
])
def test_driver_line_without_override(models, rules, expected):
    assert expected in driver_line(score_with(models, rules))


def test_low_everything_has_no_driver_line():
    assert driver_line(score_with((0.1, 0.1, 0.1), 0.1)) is None


def test_facts_include_the_driver_line():
    state = {"score": score_with((0.09, 0.13, 0.06), 1.0, "EXTREME_AMOUNT_OVERRIDE")}
    assert "**What drove the rating:**" in build_facts(state)


def test_persona_note_flags_a_synthetic_identity_label_on_an_old_card():
    from agent.report import persona_note

    s = make_score("HIGH", 0.85, ["EXTREME_AMOUNT"], "SYNTHETIC_IDENTITY", "Synthetic Identity Fraud")
    assert "24 months" in persona_note(s, {"card_age_months": 24})
    assert persona_note(s, {"card_age_months": 2}) is None
    other = make_score("HIGH", 0.85, [], "CARD_TESTING", "Card Testing Attack")
    assert persona_note(other, {"card_age_months": 24}) is None


def test_facts_show_the_data_note_and_label_shap_as_ensemble_only():
    state = {"transaction": {"amount": 1, "merchant_category": "x", "location": "y", "time_of_day": "z",
                             "transactions_last_24h": 1, "card_age_months": 24, "device_match": "d"},
             "score": make_score("HIGH", 0.85, ["EXTREME_AMOUNT"], "SYNTHETIC_IDENTITY", "Synthetic Identity Fraud"),
             "shap": {"narrative": "n"}}
    facts = build_facts(state)
    assert "**Data note:**" in facts and "SHAP drivers (ensemble model only)" in facts


def test_render_actions_copies_steps_verbatim_and_uses_default_reasons():
    from agent.report import render_actions

    hit = {"doc_id": "POL-001", "title": "Card Testing", "matched_rules": ["MICRO_TRANSACTION_CARD_TEST"],
           "matched_personas": [], "required_actions": ["Place a hold.", "Call the customer."]}
    out = render_actions([hit], {})
    assert "- **[POL-001] Card Testing**: matches the triggered rule(s) MICRO_TRANSACTION_CARD_TEST" in out
    assert "  - Place a hold." in out and "  - Call the customer." in out


def test_persona_contradicted_only_for_synthetic_identity_on_an_established_card():
    from agent.report import persona_contradicted

    assert persona_contradicted("SYNTHETIC_IDENTITY", {"card_age_months": 24})
    assert not persona_contradicted("SYNTHETIC_IDENTITY", {"card_age_months": 2})
    assert not persona_contradicted("SYNTHETIC_IDENTITY", None)
    assert not persona_contradicted("ACCOUNT_TAKEOVER", {"card_age_months": 24})


def test_retrieval_personas_modes():
    from agent.report import retrieval_personas

    ps = [{"type": "SYNTHETIC_IDENTITY"}, {"type": "ACCOUNT_TAKEOVER"}]
    old = {"card_age_months": 36}
    assert [p["type"] for p in retrieval_personas(ps, old, "gated")] == ["ACCOUNT_TAKEOVER"]
    assert [p["type"] for p in retrieval_personas(ps, old, "all")] == ["SYNTHETIC_IDENTITY", "ACCOUNT_TAKEOVER"]
    assert retrieval_personas(ps, old, "off") == []
    assert [p["type"] for p in retrieval_personas(ps, {"card_age_months": 1}, "gated")] == ["SYNTHETIC_IDENTITY", "ACCOUNT_TAKEOVER"]
