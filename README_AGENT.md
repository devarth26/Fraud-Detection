# FraudShield Investigation Agent

An analyst asks *"Why was this transaction flagged, and what should I do?"* A LangGraph agent classifies the question, picks tools,
retrieves fraud policy (RAG), drafts a report, and pauses for a human decision on high-risk cases.

```
question ─► classify_query ─► plan_tools ─► run_data_tools ─► retrieve_policy ─► draft_report
              (LLM+fallback)   (LLM+fallback)  lookup_transaction (SQL)  (LangChain RAG)   (facts by code,
                                               score_transaction          hybrid retriever   assessment + policy choice by LLM,
                                               explain_shap               over POL-001..010  steps copied from policies by code)
                                               get_card_history (SQL)     + past case notes        │
                                                                                          HIGH risk / score ≥ 0.75?
                                                                                     yes ◄──────────┴──────────► no
                                                                               human_review (interrupt)            │
                                                                               approve / escalate / dismiss        │
                                                                                          └────────► finalize ◄────┘
                                                                                                   (case saved to PostgreSQL)
```

## What's in this zip (it is an overlay: unzip it over your repo root)
| Path | Status | Purpose |
|---|---|---|
| `agent/` | new | LangGraph graph, nodes, planner, tools, report builder, case storage |
| `rag/` | new | LangChain loaders, chunking, embeddings, hybrid retriever, optional S3 loading |
| `policies/` | new | 10 policies + 3 case notes. **I wrote these as illustrative examples; they are not real institutional policy.** |
| `api/scoring.py`, `api/agent_routes.py` | new | Side-effect-free scoring + `/score`, `/agent/*` endpoints |
| `api/main.py` | **replaced** | Your file with 4 small edits (see diff below) |
| `eval/` | new | 20 labelled cases + runner |
| `tests/` | new | 95 tests, no model files, LLM or API key needed |
| `docker/Dockerfile`, `.dockerignore`, `docker-compose.yml` | **replaced/new** | Slim image, no secrets baked in |
| `requirements-deploy.txt`, `requirements-dev.txt`, `requirements-ci.txt` | new | Slim runtime set, dev set (+pytest/ruff), light CI set (your `requirements.txt` is untouched) |
| `.github/workflows/ci-cd.yml` | new | lint → tests → eval smoke test → build → ECR → ECS → smoke test |
| `deploy/aws/README.md`, `scripts/` | new | AWS runbook, S3 sync, post-deploy smoke test |
| `docs/` | new | `KNOWN_ISSUES.md` (**read first**), `INTERVIEW_NOTES.md` |

Edits to `api/main.py`: import `agent_routes` and `scoring`, `app.include_router(agent_router)`, and `hash(...)` → `card_id_for(...)` / `history_encoders(...)`.

## LLM: local Llama 3.1 through Ollama
The agent uses an LLM for three things: classifying the question, choosing tools, and writing the assessment. Each has a deterministic fallback,
so the agent still works without one. **That also means a broken LLM is easy to miss**, so check `GET /agent/health` (`llm_ready`) and the
`intent_source` / `plan_source` / `narrative_source` fields in every response: they must say `"llm"`, not `"heuristic"` / `"template"`.

```bash
brew install ollama            # or install the Ollama app from ollama.com
ollama serve                   # skip if the app is already running
ollama pull llama3.1           # about 5 GB (the 8B model); Ollama never downloads models implicitly
```
- A local 8B model is **slower and less reliable than a hosted 70B**. JSON mode is switched on for the planning calls and every LLM output is validated, with fallbacks, but expect more fallbacks than with a large hosted model.
- Memory matters: the 8B model, your PyTorch models and the embedding model share the Mac's RAM.
- Provider switch: `LLM_PROVIDER=ollama | groq | bedrock | none`. `/predict` (the original endpoint) still uses Groq for its own analyst text; only the agent uses `LLM_PROVIDER`.
- **Ollama does not fit on a small Fargate task.** For the AWS deployment, use `LLM_PROVIDER=bedrock` (or `groq`), or host Ollama on a separate machine and set `OLLAMA_BASE_URL`.

## Run it locally
```bash
unzip fraudshield-agent.zip -d .            # from your repo root, overwrite when asked
source venv/bin/activate
pip install -r requirements-dev.txt         # runtime deps + pytest/ruff (adds langgraph, langchain-*, sentence-transformers, ...)
cat .env.agent.example >> .env              # sets the local Llama 3.1 (Ollama) provider; contains no key line
echo -e "\neval/results/\n*.db" >> .gitignore
uvicorn api.main:app --reload --port 8000
```
The first start downloads the embedding model (~90 MB) and builds the policy index in memory.

```bash
# Ask the agent (inline transaction; or use "transaction_id": 42 to look one up in PostgreSQL)
curl -s localhost:8000/agent/investigate -H 'content-type: application/json' -d '{
  "query": "Why was this transaction flagged, and what should I do?",
  "transaction": {"amount": 75000, "merchant_category": "Online transfer", "location": "International",
                  "time_of_day": "Evening", "transactions_last_24h": 2, "card_age_months": 24,
                  "device_match": "Known device, matching IP"}}' | python -m json.tool

# High-risk cases return "status": "pending_review" and a thread_id. Record the analyst's decision:
curl -s localhost:8000/agent/review/<thread_id> -H 'content-type: application/json' \
  -d '{"decision": "escalate", "note": "Linked accounts found"}'
```
Other endpoints: `POST /score` (read-only scoring), `GET /agent/cases`, `GET /agent/health`.

## Tests and evaluation
```bash
EMBEDDINGS_PROVIDER=hashing LLM_PROVIDER=none DATABASE_URL=sqlite:///./t.db python -m pytest -q
python -m eval.run_eval                  # REAL models + REAL LLM: the only numbers worth quoting
python -m eval.run_eval --no-llm         # fallback planner only
python -m eval.run_eval --stub-models    # pipeline check without model files (not model performance)
```

## What I tested, and what I could not
**Tested here:** all 95 unit tests (planner, graph branches, pause/resume, citation stripping, retrieval, API, S3 download logic); lint; the full 20-case evaluation
run through your real `api/main.py` rule engine, persona classifier and orchestration with the model layer stubbed, using the dependency-free embedder and no LLM.

**Not tested (no access from my environment):** your trained model artifacts, real Ollama / Llama 3.1 calls (the HTTP requests are verified against Ollama's documented API with a mocked server, never a live one), the HuggingFace embedding model, PostgreSQL (SQL lookups and the
Postgres checkpointer), the Docker build, GitHub Actions, and AWS. Expect to debug some of these on first run, especially the Docker image (large dependencies) and IAM.

## Your remaining work (and why it is yours)
1. **Read `docs/KNOWN_ISSUES.md`** and decide what to fix. Items 2-5 affect how defensible the explanations are.
2. **Review and extend `eval/cases.jsonl`.** I wrote the labels and then fixed three bugs the eval exposed, so these 20 cases are a regression suite, not an unbiased test set.
   Add cases from real flagged transactions, then run `python -m eval.run_eval` with your real models and Ollama running.
3. **Deploy** following `deploy/aws/README.md`, and check the cost notes first.
4. **Resume line, only with your real numbers** from step 2, for example: *"Built a LangGraph agent with a LangChain RAG layer over fraud policy documents on top of
   a PyTorch BiLSTM + ensemble fraud model; FastAPI on AWS ECS with GitHub Actions CI/CD; evaluated on N labelled cases (X% correct tool selection, Y% correct policy citation)."*
   Your BiLSTM was already PyTorch, so there was no port to do; list PyTorch as existing experience.
