"""Intent classification and tool planning.

Both steps ask the LLM first and validate its JSON; if the LLM is unavailable or returns
something unusable, a deterministic heuristic takes over. The `*_source` fields in the state
record which path was used, so evaluation can report them separately.
"""
from __future__ import annotations

import re

from .llm import invoke_text, parse_json_object
from .tools import TOOL_DESCRIPTIONS

INTENT_DESCRIPTIONS = {
    "full_investigation": "Analyst wants to know why a transaction was flagged AND what to do about it.",
    "explain_flag": "Analyst only wants the reasons behind the model's decision.",
    "recommend_action": "Analyst only wants next steps / what to do with the transaction.",
    "history_check": "Analyst wants the card's past behaviour or baseline, not a fraud verdict.",
    "policy_question": "General question about fraud policy or procedure, not tied to one transaction.",
}

INTENT_TOOLS = {
    "full_investigation": ["score_transaction", "explain_shap", "get_card_history", "search_policy"],
    "explain_flag": ["score_transaction", "explain_shap"],
    "recommend_action": ["score_transaction", "search_policy"],
    "history_check": ["get_card_history"],
    "policy_question": ["search_policy"],
}

# Minimum tools without which an answer to that kind of question is not valid. The LLM may add to these
# (e.g. card history) but cannot drop them: an 8B model was observed skipping explain_shap for a
# "why was it flagged" question. Corrections are recorded (plan_added) so evaluation can report them.
INTENT_REQUIRED = {
    "full_investigation": ["score_transaction", "explain_shap", "get_card_history", "search_policy"],
    "explain_flag": ["score_transaction", "explain_shap"],
    "recommend_action": ["score_transaction", "search_policy"],
    "history_check": ["get_card_history"],
    "policy_question": ["search_policy"],
}
# Single-purpose intents must not pick up extra tools. Llama 3.1 8B was observed adding
# score_transaction to a pure history question.
INTENT_ALLOWED = {
    "history_check": ["get_card_history"],
    "policy_question": ["search_policy"],
}


# def apply_required_tools(tools: list[str], intent: str) -> tuple[list[str], list[str]]:
#     """Clamp single-purpose intents, then add any tool the intent cannot do without."""
#     allowed = INTENT_ALLOWED.get(intent)
#     if allowed is not None:
#         tools = [t for t in tools if t in allowed]
#     added = [t for t in INTENT_REQUIRED[intent] if t not in tools]
#     return [t for t in PLANNABLE if t in set(tools) | set(added)], added

TOOL_ORDER = ["lookup_transaction", "score_transaction", "explain_shap", "get_card_history", "search_policy"]
PLANNABLE = [t for t in TOOL_ORDER if t != "lookup_transaction"]  # lookup is added automatically
NEEDS_TRANSACTION = {"score_transaction", "explain_shap", "get_card_history"}

_TX_ID_RE = re.compile(r"(?:\b(?:transaction|txn|tx|id)\b\s*(?:#|no\.?|number|:)?\s*(\d{1,12}))|(?:#(\d{1,12}))", re.IGNORECASE)

_WHY = ["why", "explain", "reason", "flagged", "flag", "what triggered", "how come"]
_ACTION = ["what should", "what do i do", "recommend", "next step", "action", "how should", "should i", "what now", "do about", "handle"]
_HISTORY = ["history", "previous", "past transactions", "baseline", "spending pattern", "behaviour", "behavior", "usually spend"]
_POLICY = ["policy", "procedure", "threshold", "sla", "service level", "guideline", "when must", "when do we", "how long", "retention"]


def extract_transaction_id(query: str) -> int | None:
    m = _TX_ID_RE.search(query or "")
    if not m:
        return None
    return int(m.group(1) or m.group(2))


def _has(q: str, words: list[str]) -> bool:
    """True if any keyword starts at a word boundary ("action" must not match inside "transaction")."""
    return any(re.search(r"\b" + re.escape(w), q) for w in words)


def heuristic_intent(query: str, has_transaction: bool) -> str:
    q = (query or "").lower()
    why = _has(q, _WHY)
    action = _has(q, _ACTION)
    history = _has(q, _HISTORY)
    policy = _has(q, _POLICY)
    if not has_transaction and (policy or not (why or action or history)):
        return "policy_question"
    if not has_transaction and action and not why and not history:
        return "policy_question"
    if history and not (why or action):
        return "history_check"
    if why and action:
        return "full_investigation"
    if why:
        return "explain_flag"
    if action:
        return "recommend_action"
    if policy:
        return "policy_question"
    return "full_investigation"


_parse_json = parse_json_object


def classify_intent(llm, query: str, has_transaction: bool) -> tuple[str, str]:
    """Returns (intent, source) where source is "llm", "guard" or "heuristic"."""
    rule = heuristic_intent(query, has_transaction)
    if llm is not None:
        catalog = "\n".join(f"- {k}: {v}" for k, v in INTENT_DESCRIPTIONS.items())
        prompt = (
            "You route questions for a fraud analyst assistant.\n"
            f"Intents:\n{catalog}\n\n"
            f"A specific transaction is attached to the request: {'yes' if has_transaction else 'no'}.\n"
            f"Analyst question: {query}\n\n"
            'Reply with JSON only, e.g. {"intent": "explain_flag"}.'
        )
        data = _parse_json(invoke_text(llm, prompt, json_mode=True))
        if data and data.get("intent") in INTENT_DESCRIPTIONS:
            intent = data["intent"]
            no_tx = not has_transaction and extract_transaction_id(query) is None
            # Guard 1: no transaction anywhere and the wording is a policy question.
            if no_tx and rule == "policy_question" and intent != "policy_question":
                return rule, "guard"
            # Guard 2: full_investigation needs both a "why" and an "action" in the question.
            if intent == "full_investigation" and rule in ("explain_flag", "recommend_action"):
                return rule, "guard"
            return intent, "llm"
    return rule, "heuristic"


def choose_tools(llm, query: str, intent: str) -> tuple[list[str], str]:
    """Pick tools for the question. Returns (tools, source); tools exclude lookup_transaction."""
    if llm is not None:
        catalog = "\n".join(f"- {t}: {TOOL_DESCRIPTIONS[t]}" for t in PLANNABLE)
        prompt = (
            "You plan tool calls for a fraud investigation assistant. Choose the tools needed to answer the "
            "question well. Start from the default plan for the detected intent; drop a tool only if its output "
            "is clearly not needed, and add one only if the question calls for it.\n"
            f"Tools:\n{catalog}\n\n"
            f"Detected intent: {intent}\nDefault plan for this intent: {INTENT_TOOLS[intent]}\n"
            f"Analyst question: {query}\n\n"
            'Reply with JSON only, e.g. {"tools": ["score_transaction", "search_policy"]}.'
        )
        data = _parse_json(invoke_text(llm, prompt, json_mode=True))
        tools = data.get("tools") if data else None
        if isinstance(tools, list):
            valid = [t for t in PLANNABLE if t in tools]
            if valid:
                return valid, "llm"
    return list(INTENT_TOOLS[intent]), "heuristic"


def apply_required_tools(tools: list[str], intent: str) -> tuple[list[str], list[str]]:
    """Add any tool the intent cannot do without. Returns (tools, names_added)."""
    added = [t for t in INTENT_REQUIRED[intent] if t not in tools]
    return [t for t in PLANNABLE if t in set(tools) | set(added)], added


def enforce_dependencies(tools: list[str], has_inline_transaction: bool, transaction_id: int | None):
    """Make the plan executable. Returns (ordered_tools, needs_input_message_or_None)."""
    chosen = set(tools)
    if "explain_shap" in chosen:
        chosen.add("score_transaction")  # SHAP values come out of the scoring call
    needs_tx = bool(chosen & NEEDS_TRANSACTION)
    if needs_tx and not has_inline_transaction:
        if transaction_id is None:
            return [], "I need a transaction to analyse. Please give a transaction id or the transaction details."
        chosen.add("lookup_transaction")
    return [t for t in TOOL_ORDER if t in chosen], None
