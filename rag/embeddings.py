"""Embedding providers for the policy retriever.

EMBEDDINGS_PROVIDER:
  huggingface (default) - sentence-transformers/all-MiniLM-L6-v2, runs locally on CPU
  bedrock               - Amazon Titan via langchain-aws (needs AWS credentials + model access)
  hashing               - dependency-free lexical embedder. Used in CI and unit tests so they
                          never download a model. It is NOT semantic; do not use it in production.
"""
from __future__ import annotations

import os

import numpy as np
from langchain_core.embeddings import Embeddings


class HashingEmbeddings(Embeddings):
    """Stateless bag-of-words / bigram hashing embedder (L2-normalised)."""

    def __init__(self, n_features: int = 2048):
        from sklearn.feature_extraction.text import HashingVectorizer

        self._vec = HashingVectorizer(
            n_features=n_features,
            alternate_sign=False,
            norm="l2",
            ngram_range=(1, 2),
            lowercase=True,
            token_pattern=r"(?u)\b[\w-]+\b",
        )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        mat = self._vec.transform(texts)
        return np.asarray(mat.todense(), dtype=np.float32).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]


def get_embeddings(provider: str | None = None) -> Embeddings:
    provider = (provider or os.getenv("EMBEDDINGS_PROVIDER", "huggingface")).lower()
    if provider == "hashing":
        return HashingEmbeddings()
    if provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(
            model_name=os.getenv("HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
            encode_kwargs={"normalize_embeddings": True},
        )
    if provider == "bedrock":
        from langchain_aws import BedrockEmbeddings

        return BedrockEmbeddings(
            model_id=os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"),
            region_name=os.getenv("AWS_REGION", "ap-south-1"),
        )
    raise ValueError(f"Unknown EMBEDDINGS_PROVIDER: {provider}")
