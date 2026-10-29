"""Hybrid policy retriever: semantic similarity + rule-code / persona metadata boosts."""
from __future__ import annotations

import os
from pathlib import Path

from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

from .embeddings import get_embeddings
from .ingest import DEFAULT_POLICY_DIR, build_vector_store

RULE_BOOST = 0.30
PERSONA_BOOST = 0.20


class PolicyRetriever:
    def __init__(self, store: InMemoryVectorStore):
        self.store = store

    @classmethod
    def build(cls, policy_dir: Path | str | None = None, embeddings: Embeddings | None = None):
        bucket = os.getenv("POLICY_S3_BUCKET")
        if bucket and not policy_dir:
            import tempfile

            from .s3 import sync_policies_from_s3

            policy_dir = Path(tempfile.mkdtemp(prefix="policies_"))
            sync_policies_from_s3(bucket, os.getenv("POLICY_S3_PREFIX", "policies/"), policy_dir)
        policy_dir = policy_dir or os.getenv("POLICY_DIR", str(DEFAULT_POLICY_DIR))
        embeddings = embeddings or get_embeddings()
        return cls(build_vector_store(embeddings, policy_dir))

    def search(
        self,
        query: str,
        k: int = 4,
        rule_codes: list[str] | None = None,
        personas: list[str] | None = None,
        include_cases: bool = True,
    ) -> list[dict]:
        """Return up to k distinct documents (best chunk per document), best first.

        Semantic similarity is the base score. Documents whose metadata lists a triggered rule
        or detected persona get a boost, so the retriever behaves sensibly even when the query
        is mostly rule codes (which a general-purpose embedding model handles poorly).
        """
        rule_set = set(rule_codes or [])
        persona_set = set(personas or [])
        raw = self.store.similarity_search_with_score(query, k=max(k * 5, 20))

        best: dict[str, dict] = {}
        for doc, sim in raw:
            m = doc.metadata
            if not include_cases and m["doc_type"] == "case":
                continue
            score = float(sim)
            rule_hits = rule_set & set(m.get("rule_codes", []))
            if rule_set and rule_hits:
                score += RULE_BOOST * len(rule_hits) / len(rule_set)
            persona_hits = persona_set & set(m.get("personas", []))
            if persona_hits:
                score += PERSONA_BOOST
            cur = best.get(m["doc_id"])
            if cur is None or score > cur["score"]:
                best[m["doc_id"]] = {
                    "doc_id": m["doc_id"],
                    "doc_type": m["doc_type"],
                    "title": m["title"],
                    "section": m.get("section", ""),
                    "text": doc.page_content,
                    "score": round(score, 4),
                    "matched_rules": sorted(rule_hits),
                    "matched_personas": sorted(persona_hits),
                    "required_actions": list(m.get("required_actions", [])),
                }
        ranked = sorted(best.values(), key=lambda d: d["score"], reverse=True)
        return ranked[:k]
