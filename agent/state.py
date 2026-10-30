import operator
from typing import Annotated, Optional, TypedDict


class InvestigationState(TypedDict, total=False):
    # inputs
    query: str
    transaction_id: Optional[int]
    transaction: Optional[dict]

    # planning
    intent: str
    intent_source: str          # "llm" | "heuristic"
    planned_tools: list[str]
    plan_source: str            # "llm" | "heuristic"
    plan_added: list[str]       # tools the floor added because the planner left them out
    plan_removed: list[str]     # extra tools the clamp removed from a single-purpose intent
    needs_input: Optional[str]  # set when the agent cannot proceed (missing/unknown transaction)

    # tool outputs
    score: Optional[dict]
    shap: Optional[dict]
    card_history: Optional[dict]
    policy_hits: list[dict]

    # derived
    risk_tier: Optional[str]
    weighted_score: Optional[float]
    needs_review: bool
    review: Optional[dict]

    # outputs
    report: str
    policies_cited: list[str]
    narrative_source: str       # "llm" | "template"  (who wrote the assessment)
    selection_source: str       # "llm" | "signals"    (who chose the applicable policies)
    status: str                 # completed | reviewed | needs_input
    case_id: Optional[int]

    # reducers: these accumulate across nodes
    tools_used: Annotated[list[str], operator.add]
    trace: Annotated[list[str], operator.add]
