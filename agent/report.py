"""Report assembly.

Facts (scores, rules, SHAP, history) and the recommended steps are rendered by code from tool output
and from the text of the retrieved policies, so they cannot be hallucinated or misattributed. The LLM
does only two things: it writes a short assessment, and it SELECTS which retrieved policies apply.
Every id it returns is checked against what was actually retrieved.
"""
from __future__ import annotations

import re

from .llm import invoke_text, parse_json_object

_CITE_RE = re.compile(r"\b(?:POL|CASE)-\d{3}\b")


def extract_citations(text: str) -> list[str]:
    seen: list[str] = []
    for m in _CITE_RE.findall(text or ""):
        if m not in seen:
            seen.append(m)
    return seen


def sanitize_citations(text: str, allowed: set[str]) -> tuple[str, list[str]]:
    """Remove references to ids that were not retrieved. Returns (clean_text, removed_ids)."""
    removed = [c for c in extract_citations(text) if c not in allowed]
    for bad in removed:
        text = re.sub(rf"\[?{re.escape(bad)}\]?", "[unverified reference removed]", text)
    return text, removed


def driver_line(score: dict) -> str | None:
    """Plain statement of WHAT produced the rating, computed from the numbers (not written by an LLM).

    The weighted score mixes learned models with a rule engine, and a hard override can force HIGH
    while every model scored low. An analyst must be able to see that at a glance.
    """
    orch = score["orchestration"]
    comp = orch["component_scores"]
    models = {"ensemble": comp["ensemble"], "LSTM": comp["lstm"], "autoencoder": comp["autoencoder"]}
    model_txt = ", ".join(f"{k} {v:.2f}" for k, v in models.items())
    models_high = max(models.values()) >= 0.5
    rules_high = comp["rules"] >= 0.5
    if orch.get("hard_override"):
        tail = "the learned models also scored high" if models_high else "the learned models did NOT flag it"
        return f"{orch['override_reason']} hard override (rule score {comp['rules']:.2f}); {tail} ({model_txt})"
    if rules_high and not models_high:
        return f"the rule engine (score {comp['rules']:.2f}); the learned models did NOT flag it ({model_txt})"
    if models_high and not rules_high:
        return f"the learned models ({model_txt}); no strong rule fired"
    if models_high and rules_high:
        return f"rules and learned models agree (rules {comp['rules']:.2f}; {model_txt})"
    return None


def persona_note(score: dict, tx: dict | None) -> str | None:
    """Flag a persona label that the transaction's own data contradicts.

    FraudShield's persona indicators are fixed strings and its synthetic-identity score is driven mostly
    by "no history on record", which is unreliable because card history is keyed by device type.
    """
    persona = score["persona"]["primary_persona"]
    age = (tx or {}).get("card_age_months")
    if persona["type"] == "SYNTHETIC_IDENTITY" and age is not None and age >= 6:
        return (f"the persona label \"{persona['label']}\" conflicts with a card age of {age} months; it is driven "
                "mainly by missing history, which is unreliable here. Treat the label with caution.")
    return None


def build_facts(state: dict) -> str:
    lines: list[str] = []
    tx = state.get("transaction")
    if tx:
        lines.append(
            "- **Transaction:** amount {amount}, {merchant_category}, {location}, {time_of_day}, "
            "{transactions_last_24h} transactions in 24h, card age {card_age_months} months, "
            "device: {device_match}".format(**tx)
        )
        stored = tx.get("stored_verdict")
        if stored:
            lines.append(
                f"- **Stored decision:** risk {stored.get('risk_tier')}, score {stored.get('confidence')}, "
                f"flagged as fraud: {stored.get('is_fraud')}"
            )
    score = state.get("score")
    if score:
        comp = score["orchestration"]["component_scores"]
        lines.append(
            f"- **Risk:** {score['risk_tier']} (weighted score {score['weighted_score']:.2f}); "
            f"components: ensemble {comp['ensemble']:.2f}, LSTM {comp['lstm']:.2f}, "
            f"autoencoder {comp['autoencoder']:.2f}, rules {comp['rules']:.2f}"
        )
        driver = driver_line(score)
        if driver:
            lines.append(f"- **What drove the rating:** {driver}")
        rules = score["rules"]["rules_triggered"]
        lines.append("- **Rules triggered:** " + (", ".join(rules) if rules else "none"))
        persona = score["persona"]["primary_persona"]
        lines.append(f"- **Fraud persona:** {persona['label']} (severity {persona['severity']})")
        note = persona_note(score, tx)
        if note:
            lines.append(f"- **Data note:** {note}")
        ens = score["ensemble"]
        lines.append(f"- **Ensemble votes:** {ens['votes']}/5 models flagged fraud")
    shap = state.get("shap")
    if shap:
        lines.append(f"- **SHAP drivers (ensemble model only):** {shap['narrative']}")
    hist = state.get("card_history")
    if hist is not None:
        if hist.get("tx_count", 0) > 0:
            lines.append(
                f"- **Card history:** {hist['tx_count']} prior transactions, average amount {hist['avg_amount']}, "
                f"average velocity {hist['avg_velocity']}/24h, {hist['merchant_diversity']} merchants, "
                f"{hist['location_diversity']} locations"
            )
        else:
            lines.append("- **Card history:** no prior transactions on record")
    return "\n".join(lines) if lines else "- No transaction data was needed for this question."


def is_benign(score: dict) -> bool:
    return (
        score["risk_tier"] == "LOW"
        and not score["rules"]["rules_triggered"]
        and score["persona"]["primary_persona"]["type"] == "UNKNOWN"
    )


def relevant_hits(hits: list[dict]) -> list[dict]:
    """Signal-based selection: hits tied to a triggered rule or detected persona; otherwise the clearly-best few."""
    tied = [h for h in hits if h.get("matched_rules") or h.get("matched_personas")]
    if tied:
        return tied[:3]
    if not hits:
        return []
    top = hits[0]["score"]
    return [h for h in hits if h["score"] >= 0.6 * top][:2]


def default_reason(hit: dict) -> str:
    if hit.get("matched_rules"):
        return "matches the triggered rule(s) " + ", ".join(hit["matched_rules"])
    if hit.get("matched_personas"):
        return "matches the detected pattern " + ", ".join(hit["matched_personas"])
    return "closest match to the question"


def render_actions(selected: list[dict], reasons: dict[str, str]) -> str:
    """Recommended actions, copied verbatim from the selected policies' "Required actions" steps."""
    lines: list[str] = []
    for h in selected:
        why = reasons.get(h["doc_id"]) or default_reason(h)
        lines.append(f"- **[{h['doc_id']}] {h['title']}**: {why}")
        lines.extend(f"  - {step}" for step in h.get("required_actions", []))
    return "\n".join(lines)


def template_assessment(state: dict) -> str:
    """Deterministic assessment used when no LLM is available (and for benign cases)."""
    score = state.get("score")
    if not score:
        return "Relevant policy guidance is listed below." if state.get("policy_hits") else "No assessment could be produced from the available data."
    persona = score["persona"]["primary_persona"]["label"]
    rules = score["rules"]["rules_triggered"]
    text = (
        f"The transaction is rated {score['risk_tier']} risk (weighted score {score['weighted_score']:.2f}). "
        f"Primary pattern: {persona}. Rules triggered: {', '.join(rules) if rules else 'none'}."
    )
    if is_benign(score):
        text += " No fraud indicators were found, so no policy action is required. Approve and continue routine monitoring."
    return text


def llm_assessment(llm, state: dict, facts: str) -> tuple[str | None, list[tuple[str, str]] | None]:
    """Ask the LLM for (assessment, selected policies). Each part is None if missing or malformed."""
    hits = state.get("policy_hits") or []
    if hits:
        sources = "\n\n".join(
            f"[{h['doc_id']}] {h['title']} (matched rules: {', '.join(h.get('matched_rules') or []) or 'none'}; "
            f"matched patterns: {', '.join(h.get('matched_personas') or []) or 'none'})\n{h['text']}"
            for h in hits
        )
    else:
        sources = "(no policy documents retrieved)"
    prompt = (
        "You are a senior fraud analyst reviewing a case. Using ONLY the verified findings and policy excerpts below, "
        "reply with JSON of this shape:\n"
        '{"assessment": "<2-3 sentences>", "applicable_policies": [{"id": "POL-001", "why": "<one short sentence tying it to THIS transaction>"}]}\n\n'
        f"Analyst question: {state.get('query')}\n\n"
        f"Verified findings:\n{facts}\n\n"
        f"Policy and case excerpts:\n{sources}\n\n"
        "Rules:\n"
        "- The assessment answers the analyst's question using only the findings. Say what drove the rating using the "
        "'What drove the rating' finding. Never describe a model that scored low, or a minority vote (for example 1 of 5), as supporting fraud.\n"
        "- SHAP drivers explain only the ensemble model's own score; they do not raise or lower the final rating.\n"
        "- Treat only signals listed in the findings as risk signals (time of day, for example, is not one unless a rule fired). "
        "Respect any Data note: do not present a caveated persona label as established fact.\n"
        "- applicable_policies: list ONLY excerpts whose scope matches this transaction (merchant type, amount, signals). "
        "Leave out the rest. Use an empty list if none apply. Use ONLY ids shown above.\n"
        "- Do not write recommended steps: they are added automatically from the policies you choose. "
        "Do not invent thresholds, numbers or facts."
    )
    data = parse_json_object(invoke_text(llm, prompt, json_mode=True))
    if not data:
        return None, None
    assessment = data.get("assessment")
    assessment = assessment.strip() if isinstance(assessment, str) and assessment.strip() else None
    selected = None
    policies = data.get("applicable_policies")
    if isinstance(policies, list):
        selected = []
        for p in policies:
            if isinstance(p, dict) and isinstance(p.get("id"), str):
                selected.append((p["id"].strip(), str(p.get("why", "")).strip()))
            elif isinstance(p, str):
                selected.append((p.strip(), ""))
    return assessment, selected


def assemble_report(state: dict, assessment: str, actions_md: str) -> str:
    hits = state.get("policy_hits") or []
    sections = [
        "# Investigation report",
        f"**Question:** {state.get('query')}",
        f"**Interpreted as:** {state.get('intent')}",
        "## Findings",
        build_facts(state),
    ]
    if state.get("needs_review"):
        sections.append("> **Human review required:** this case is HIGH risk. No permanent block or report may be filed until an analyst records a decision.")
    sections += ["## Assessment", assessment]
    if actions_md:
        sections += ["## Recommended actions (steps copied from the selected policies)", actions_md]
    if hits:
        sections.append("## Policy references retrieved")
        sections.append("\n".join(f"- [{h['doc_id']}] {h['title']} (relevance {h['score']:.2f})" for h in hits))
    return "\n\n".join(sections)


def review_section(review: dict) -> str:
    note = review.get("note") or "(no note provided)"
    return f"## Analyst review\n- **Decision:** {review['decision']}\n- **Note:** {note}"
