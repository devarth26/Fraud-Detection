"""Evaluate the agent on labelled cases.

    python -m eval.run_eval                      # real models + real LLM (the numbers to quote)\n                                                 # (a local Llama 3.1 run takes a while: ~3 LLM calls per case)
    python -m eval.run_eval --no-llm             # heuristic planner only (the fallback path)
    python -m eval.run_eval --stub-models        # no model artifacts needed; pipeline check only

Metrics
  intent accuracy          classified intent == expected
  tool-set exact match     tools used == expected set (lookup_transaction ignored)
  tool precision / recall  micro-averaged over all cases
  retrieval hit            at least one expected policy was retrieved (cases with a must_cite_any list)
  citation hit             at least one expected policy is cited in the final report
  irrelevant citation rate cited ids that are outside the case's `relevant` list
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load_cases(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(service, cases: list[dict], sleep: float = 0.0) -> list[dict]:
    rows = []
    for c in cases:
        resp = service.investigate(c["query"], transaction=c.get("transaction"))
        if resp["status"] == "pending_review":  # high-risk case: auto-approve so the run can finish
            resp = service.review(resp["thread_id"], "approve", "automated evaluation run")
        used = {t for t in resp["tools_used"] if t != "lookup_transaction"}
        expected = set(c["expected_tools"])
        must = set(c.get("must_cite_any", []))
        cited = set(resp["policies_cited"])
        relevant = set(c.get("relevant", []))
        rows.append({
            "id": c["id"],
            "query": c["query"],
            "intent": resp["intent"],
            "intent_ok": resp["intent"] == c["expected_intent"],
            "intent_source": resp["intent_source"],
            "plan_source": resp["plan_source"],
            "plan_added": resp.get("plan_added", []),
            "plan_removed": resp.get("plan_removed", []),
            "narrative_source": resp["narrative_source"],
            "tools_used": sorted(used),
            "tools_expected": sorted(expected),
            "tools_exact": used == expected,
            "tp": len(used & expected), "fp": len(used - expected), "fn": len(expected - used),
            "has_policy_label": bool(must),
            "retrieval_hit": bool(must & set(resp["policies_retrieved"])) if must else None,
            "citation_hit": bool(must & cited) if must else None,
            "cited": sorted(cited),
            "cited_irrelevant": sorted(cited - relevant) if relevant else [],
            "risk_tier": resp["risk_tier"],
            "status": resp["status"],
        })
        if sleep:
            time.sleep(sleep)
    return rows


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    tp, fp, fn = (sum(r[k] for r in rows) for k in ("tp", "fp", "fn"))
    labelled = [r for r in rows if r["has_policy_label"]]
    cited_total = sum(len(r["cited"]) for r in rows if r["has_policy_label"])
    irrelevant_total = sum(len(r["cited_irrelevant"]) for r in rows if r["has_policy_label"])
    pct = lambda a, b: round(100 * a / b, 1) if b else None  # noqa: E731
    return {
        "cases": n,
        "intent_accuracy_pct": pct(sum(r["intent_ok"] for r in rows), n),
        "tool_set_exact_match_pct": pct(sum(r["tools_exact"] for r in rows), n),
        "tool_precision_pct": pct(tp, tp + fp),
        "tool_recall_pct": pct(tp, tp + fn),
        "policy_labelled_cases": len(labelled),
        "retrieval_hit_pct": pct(sum(r["retrieval_hit"] for r in labelled), len(labelled)),
        "citation_hit_pct": pct(sum(r["citation_hit"] for r in labelled), len(labelled)),
        "irrelevant_citation_rate_pct": pct(irrelevant_total, cited_total),
        # How often the LLM actually did the work. Near 0 with an LLM configured means it is failing silently.
        "llm_intent_pct": pct(sum(r["intent_source"] == "llm" for r in rows), n),
        "llm_plan_pct": pct(sum(r["plan_source"] == "llm" for r in rows), n),
        "plan_corrected_pct": pct(sum(bool(r["plan_added"] or r["plan_removed"]) for r in rows), n),
        # What the LLM did on its own, before any code correction (intent guards are visible via intent_source):
        "tool_set_exact_llm_only_pct": pct(
            sum(((set(r["tools_used"]) - set(r["plan_added"])) | set(r["plan_removed"])) == set(r["tools_expected"]) for r in rows), n),
        "llm_intent_correct_pct": pct(sum(r["intent_source"] == "llm" and r["intent_ok"] for r in rows), n),
        "llm_narrative_pct": pct(sum(r["narrative_source"] == "llm" for r in rows if r["narrative_source"]), n),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(ROOT / "eval" / "cases.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "eval" / "results"))
    ap.add_argument("--no-llm", action="store_true", help="force the deterministic fallback planner/narrative")
    ap.add_argument("--stub-models", action="store_true", help="use fake model scores (pipeline check only)")
    ap.add_argument("--sleep", type=float, default=1.0, help="seconds between cases when an LLM is used (rate limits)")
    args = ap.parse_args()

    if args.no_llm:
        os.environ["LLM_PROVIDER"] = "none"
    if args.stub_models:
        os.environ.setdefault("DATABASE_URL", "sqlite:///./eval_stub.db")
        os.environ.setdefault("GROQ_API_KEY", "stub-not-used")  # api.main builds a Groq client at import
        from eval import stub_models
        stub_models.install()

    from agent.llm import get_llm, llm_preflight, ollama_settings, provider_name
    from agent.service import InvestigationService

    llm_on = get_llm() is not None
    if llm_on:
        ready, detail = llm_preflight()
        if not ready:
            sys.exit(f"LLM preflight failed: {detail}\nFix this, or pass --no-llm to evaluate the fallback path on purpose.")
    service = InvestigationService.create()
    rows = evaluate(service, load_cases(Path(args.cases)), sleep=args.sleep if llm_on else 0.0)
    summary = summarise(rows)
    meta = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "llm_provider": (provider_name() + (f" / {ollama_settings()['model']}" if provider_name() == "ollama" else ""))
        if llm_on else "none (heuristic fallback)",
        "embeddings": os.getenv("EMBEDDINGS_PROVIDER", "huggingface"),
        "models": "STUB (not real model scores)" if args.stub_models else "real FraudShield artifacts",
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (out / f"eval_{stamp}.json").write_text(json.dumps({"meta": meta, "summary": summary, "rows": rows}, indent=2))

    print(f"\nconfig: {meta}\n")
    print(f"{'id':5} {'intent':20} {'tools':6} {'retr':5} {'cite':5} cited")
    for r in rows:
        flag = lambda v: "-" if v is None else ("ok" if v else "MISS")  # noqa: E731
        print(f"{r['id']:5} {r['intent']:20} {'ok' if r['tools_exact'] else 'MISS':6} "
              f"{flag(r['retrieval_hit']):5} {flag(r['citation_hit']):5} {','.join(r['cited'])}")
    print("\n" + json.dumps(summary, indent=2))
    if args.stub_models:
        print("\nNOTE: --stub-models run. Do not quote these numbers as model performance.")


if __name__ == "__main__":
    main()
