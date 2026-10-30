# Defending this project

## 30-second pitch
"An analyst asks why a transaction was flagged. A LangGraph agent classifies the question, chooses which tools to run (the FraudShield scorer, a SQL
lookup, SHAP, card history, policy search), retrieves the relevant fraud policy with a hybrid RAG retriever, and drafts a report in which every
cited policy is verified against what was actually retrieved. High-risk cases pause for a human decision before they are finalised."

## Design decisions you should be able to explain
- **Why a graph, not a chain?** Branching (needs input / not found / needs review), a pause-and-resume human step, and tool selection that varies per question.
- **Why is the report built mostly by code?** Scores, rules and SHAP drivers are rendered straight from tool output, so they cannot be hallucinated. The LLM does two small things: writes a 2-3 sentence assessment and *selects* which retrieved policies apply. The recommended steps are copied verbatim from the selected policies.
- **Why not let the LLM write the recommended actions?** I tried: with a local 8B model it repeated one policy for every step, attributed steps to policies that do not say them, and ignored the most specific rule (a two-analyst approval above a threshold). Prompt rules did not fix it; shrinking the task to *selection* did.
- **How do you stop hallucinated citations?** Every policy id the LLM returns, in its selection or its text, is checked against the retrieved set; unknown ids are dropped and logged. If it selects nothing for a flagged case, rule/persona signals choose instead.
- **Why hybrid retrieval?** Embeddings handle rule codes like `MICRO_TRANSACTION_CARD_TEST` poorly. Documents declare the rule codes and personas they cover, and the retriever boosts matches.
- **Why `interrupt()` + a checkpointer?** The graph state is saved at the review step and resumed when the analyst responds; a durable checkpointer (Postgres) is needed for more than one container.
- **Why a pure `score_transaction()`?** `/predict` writes to the DB and calls an LLM; the agent needs to re-score without side effects.
- **Graceful degradation:** with no LLM or on any LLM error, the planner and narrative fall back to deterministic logic; tool failures are recorded, not fatal.
- **Why a local Llama 3.1 via Ollama?** No data leaves the machine (relevant for financial data) and no API cost. The trade-off is speed and reliability of a small model, which is why the planning calls use JSON mode and all output is validated.
- **How do you know the LLM is really being used?** Every response records `intent_source` / `plan_source` / `narrative_source`; `/agent/health` runs a preflight; the evaluation refuses to run if the LLM is unreachable and reports the share of cases where the LLM did the work.

## How did you test it?
- 95 unit tests with fakes for the models, DB and LLM (planner, graph paths, pause/resume, citation stripping, retrieval, API, S3 sync).
- A 20-case labelled evaluation (`python -m eval.run_eval`) reporting intent accuracy, tool-set match, tool precision/recall, retrieval hit and citation hit.
- **Be honest about it:** the labels are yours/hand-written, the cases double as regression tests, and numbers from `--stub-models` or `--no-llm` must not be quoted as the system's performance. Add cases from real flagged transactions.

## Questions to expect, and honest answers
- *"Is the data real?"* No, it is synthetic; the point is the architecture. (See KNOWN_ISSUES #1.)
- *"What would you do first to improve it?"* Fix the schema (real card id), verify the LSTM feature pipeline, add authentication, and grow the evaluation set from real cases.
- *"What are the agent's failure modes?"* Wrong intent routing (measured), retrieval missing a relevant policy (measured), and the underlying scores being wrong (not measured by the agent evaluation).
