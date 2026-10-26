"""LLM access for the agent. Returns None when no provider is configured, and every caller has
a deterministic fallback, so the agent degrades gracefully instead of crashing.

LLM_PROVIDER: groq (default) | bedrock | none
"""
from __future__ import annotations

import os
from types import SimpleNamespace


class GroqChat:
    """Minimal chat wrapper over the `groq` SDK that FraudShield already uses.

    Deliberately not langchain-groq: every langchain-groq release requires groq<1.0, which conflicts
    with the groq 1.x pinned in this project. The agent only needs .invoke(prompt) -> .content.
    """

    def __init__(self, api_key: str, model: str, temperature: float = 0.0, max_tokens: int = 700, client=None):
        if client is None:
            from groq import Groq

            client = Groq(api_key=api_key)
        self._client = client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def invoke(self, prompt: str):
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return SimpleNamespace(content=response.choices[0].message.content or "")


def get_llm():
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    if provider == "none":
        return None
    if provider == "groq":
        key = os.getenv("GROQ_API_KEY")
        if not key:
            return None
        return GroqChat(
            api_key=key,
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        )
    if provider == "bedrock":
        from langchain_aws import ChatBedrockConverse

        return ChatBedrockConverse(
            model=os.environ["BEDROCK_MODEL_ID"],
            region_name=os.getenv("AWS_REGION", "ap-south-1"),
            temperature=0,
            max_tokens=700,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def invoke_text(llm, prompt: str) -> str | None:
    """Call the LLM and return plain text, or None on any failure (callers then fall back)."""
    if llm is None:
        return None
    try:
        response = llm.invoke(prompt)
        content = getattr(response, "content", response)
        if isinstance(content, list):  # some providers return content blocks
            content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
        content = str(content).strip()
        return content or None
    except Exception:
        return None
