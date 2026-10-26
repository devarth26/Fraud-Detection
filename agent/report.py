"""Report assembly.

Facts (scores, rules, SHAP, history, retrieved policies) are rendered by code straight from tool
outputs, so they cannot be hallucinated. The LLM only writes the assessment and recommended
actions, and every policy id it cites is checked against what was actually retrieved.
"""
from __future__ import annotations

import re

from .llm import invoke_text

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
        if score["orchestration"].get("hard_override"):
            lines.append(f"- **Hard override applied:** {score['orchestration']['override_reason']}")
        rules = score["rules"]["rules_triggered"]
        lines.append("- **Rules triggered:** " + (", ".join(rules) if rules else "none"))
        persona = score["persona"]["primary_persona"]
        lines.append(f"- **Fraud persona:** {persona['label']} (severity {persona['severity']})")
        ens = score["ensemble"]
        lines.append(f"- **Ensemble votes:** {ens['votes']}/5 models flagged fraud")
    shap = state.get("shap")
    if shap:
        lines.append(f"- **SHAP drivers:** {shap['narrative']}")
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


def _first_action(text: str) -> str | None:
    for line in text.splitlines():
        m = re.match(r"^\s*\d+\.\s+(.*)", line)
        if m:
            return m.group(1).strip()
    return None


def _is_benign(score: dict) -> bool:
    return (
        score["risk_tier"] == "LOW"
        and not score["rules"]["rules_triggered"]
        and score["persona"]["primary_persona"]["type"] == "UNKNOWN"
    )


def _relevant_hits(hits: list[dict]) -> list[dict]:
    """Hits tied to a triggered rule or detected persona; otherwise the clearly-best few."""
    tied = [h for h in hits if h.get("matched_rules") or h.get("matched_personas")]
    if tied:
        return tied[:3]
    if not hits:
        return []
    top = hits[0]["score"]
    return [h for h in hits if h["score"] >= 0.6 * top][:2]


def template_narrative(state: dict) -> str:
    """Deterministic narrative used when no LLM is available."""
    hits = state.get("policy_hits") or []
    score = state.get("score")
    parts: list[str] = []
    if score:
        persona = score["persona"]["primary_persona"]["label"]
        rules = score["rules"]["rules_triggered"]
        parts.append(
            f"The transaction is rated {score['risk_tier']} risk (weighted score {score['weighted_score']:.2f}). "
            f"Primary pattern: {persona}. Rules triggered: {', '.join(rules) if rules else 'none'}."
        )
        if _is_benign(score):
            parts.append("No fraud indicators were found, so no policy action is required. Approve and continue routine monitoring.")
            return "\n".join(parts)
    chosen = _relevant_hits(hits)
    if chosen:
        parts.append("Recommended actions:")
        for h in chosen:
            action = _first_action(h["text"])
            detail = f": {action}" if action else ""
            parts.append(f"- Apply [{h['doc_id']}] {h['title']}{detail}")
    elif score:
        parts.append("No matching policy was retrieved; escalate to a senior analyst for guidance.")
    if state.get("needs_review"):
        parts.append("This case requires analyst review before any permanent block or report is filed.")
    return "\n".join(parts) if parts else "No assessment could be produced from the available data."


def llm_narrative(llm, state: dict, facts: str) -> str | None:
    hits = state.get("policy_hits") or []
    if hits:
        sources = "\n\n".join(f"[{h['doc_id']}] {h['title']}\n{h['text']}" for h in hits)
    else:
        sources = "(no policy documents retrieved)"
    prompt = (
        "You are a senior fraud analyst writing the assessment section of an investigation report.\n\n"
        f"Analyst question: {state.get('query')}\n\n"
        f"Verified findings from tools:\n{facts}\n\n"
        f"Policy and case excerpts you may cite:\n{sources}\n\n"
        "Write:\n"
        "1. Assessment: 2-3 sentences answering the question using only the findings above.\n"
        "2. Recommended actions: a numbered list of at most 5 concrete steps.\n\n"
        "Rules: cite sources inline like [POL-001] or [CASE-002] using ONLY ids shown above. "
        "Do not invent thresholds, numbers or facts. If the excerpts do not cover something, say so. "
        "Keep it under 220 words."
    )
    return invoke_text(llm, prompt)


def assemble_report(state: dict, narrative: str) -> str:
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
    sections += [
        "## Assessment and recommended actions",
        narrative,
    ]
    if hits:
        sections.append("## Policy references retrieved")
        sections.append("\n".join(f"- [{h['doc_id']}] {h['title']} (relevance {h['score']:.2f})" for h in hits))
    return "\n\n".join(sections)


def review_section(review: dict) -> str:
    note = review.get("note") or "(no note provided)"
    return f"## Analyst review\n- **Decision:** {review['decision']}\n- **Note:** {note}"
