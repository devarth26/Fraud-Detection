"""LLM access for the agent. Returns None when no provider is configured, and every caller has
a deterministic fallback, so the agent degrades gracefully instead of crashing.

LLM_PROVIDER: ollama (default, local Llama 3.1) | groq | bedrock | none
"""
from __future__ import annotations

import json
import logging
import os
import re
from types import SimpleNamespace

logger = logging.getLogger("agent.llm")

DEFAULT_OLLAMA_MODEL = "llama3.1"  # resolves to the :latest tag (the 8B model)
DEFAULT_OLLAMA_URL = "http://localhost:11434"


class OllamaChat:
    """Chat client for a local Ollama server (https://ollama.com), using its REST API directly.

    Uses httpx (already a dependency) instead of an extra SDK. Two details matter for this agent:
      * num_ctx: Ollama defaults to a 2048-token context window and silently truncates longer
        prompts; the report prompt (facts + policy excerpts) can exceed that, so it is raised.
      * json_mode: format="json" forces syntactically valid JSON, which small local models need
        for the intent / tool-planning calls.
    """

    supports_json_mode = True

    def __init__(self, model: str = DEFAULT_OLLAMA_MODEL, base_url: str = DEFAULT_OLLAMA_URL, temperature: float = 0.0,
                 max_tokens: int = 700, num_ctx: int = 4096, keep_alive: str = "30m", timeout: float = 180.0, client=None):
        import httpx

        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        self._client = client or httpx.Client(timeout=timeout)

    def invoke(self, prompt: str, json_mode: bool = False):
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens, "num_ctx": self.num_ctx},
        }
        if json_mode:
            payload["format"] = "json"
        response = self._client.post(f"{self.base_url}/api/chat", json=payload)
        response.raise_for_status()
        return SimpleNamespace(content=response.json()["message"]["content"])


class GroqChat:
    """Minimal chat wrapper over the `groq` SDK that FraudShield already uses.

    Deliberately not langchain-groq: every langchain-groq release requires groq<1.0, which conflicts
    with the groq 1.x pinned in this project. The agent only needs .invoke(prompt) -> .content.
    """

    supports_json_mode = False

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


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_object(text: str | None) -> dict | None:
    """Extract the first JSON object from LLM output; None if there isn't a valid one."""
    if not text:
        return None
    match = _JSON_OBJECT_RE.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def provider_name() -> str:
    return os.getenv("LLM_PROVIDER", "ollama").lower()


def ollama_settings() -> dict:
    return {
        "model": os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        "base_url": os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL),
    }


def get_llm():
    provider = provider_name()
    if provider == "none":
        return None
    if provider == "ollama":
        cfg = ollama_settings()
        return OllamaChat(
            model=cfg["model"],
            base_url=cfg["base_url"],
            num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "4096")),
            keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
            timeout=float(os.getenv("OLLAMA_TIMEOUT", "180")),
        )
    if provider == "groq":
        key = os.getenv("GROQ_API_KEY")
        if not key:
            return None
        return GroqChat(api_key=key, model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
    if provider == "bedrock":
        from langchain_aws import ChatBedrockConverse

        return ChatBedrockConverse(
            model=os.environ["BEDROCK_MODEL_ID"],
            region_name=os.getenv("AWS_REGION", "ap-south-1"),
            temperature=0,
            max_tokens=700,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def llm_preflight(client=None) -> tuple[bool, str]:
    """Is the configured LLM actually usable right now? Returns (ready, human-readable detail).

    LLM failures are deliberately non-fatal inside the agent (it falls back to deterministic logic),
    which also means a broken LLM is invisible. This check makes it visible in /agent/health and
    stops the evaluation from reporting fallback results as LLM results.
    """
    provider = provider_name()
    if provider == "none":
        return False, "LLM disabled (LLM_PROVIDER=none)"
    if provider == "ollama":
        import httpx

        cfg = ollama_settings()
        try:
            c = client or httpx.Client(timeout=5)
            resp = c.get(f"{cfg['base_url'].rstrip('/')}/api/tags")
            resp.raise_for_status()
            names = [m.get("name", "") for m in resp.json().get("models", [])]
        except Exception as exc:
            return False, f"Ollama not reachable at {cfg['base_url']} ({type(exc).__name__}). Start it with: ollama serve"
        wanted = cfg["model"]
        if wanted in names or (":" not in wanted and f"{wanted}:latest" in names):
            return True, f"Ollama ready, model {wanted}"
        return False, f"Ollama is running but model {wanted} is not pulled. Run: ollama pull {wanted}"
    if provider == "groq":
        return (True, "Groq key present (not verified)") if os.getenv("GROQ_API_KEY") else (False, "GROQ_API_KEY not set")
    return (True, f"{provider} configured (not verified)")


def invoke_text(llm, prompt: str, json_mode: bool = False) -> str | None:
    """Call the LLM and return plain text, or None on any failure (callers then fall back).

    Failures are logged so a broken LLM is visible in the server log instead of silently degrading.
    """
    if llm is None:
        return None
    try:
        if json_mode and getattr(llm, "supports_json_mode", False):
            response = llm.invoke(prompt, json_mode=True)
        else:
            response = llm.invoke(prompt)
        content = getattr(response, "content", response)
        if isinstance(content, list):  # some providers return content blocks
            content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
        content = str(content).strip()
        return content or None
    except Exception as exc:
        logger.warning("LLM call failed, using fallback: %s: %s", type(exc).__name__, exc)
        return None
