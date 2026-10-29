from types import SimpleNamespace

from agent.llm import GroqChat, get_llm, invoke_text


class FakeGroqClient:
    def __init__(self, text="hello", fail=False):
        self.calls = []
        outer = self

        class Completions:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                if fail:
                    raise RuntimeError("rate limited")
                msg = SimpleNamespace(content=text)
                return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

        self.chat = SimpleNamespace(completions=Completions())


def test_groq_chat_sends_prompt_and_returns_content():
    client = FakeGroqClient("hi there")
    llm = GroqChat(api_key="k", model="m", client=client)
    out = llm.invoke("question?")
    assert out.content == "hi there"
    call = client.calls[0]
    assert call["model"] == "m" and call["temperature"] == 0.0
    assert call["messages"] == [{"role": "user", "content": "question?"}]


def test_invoke_text_returns_none_when_groq_raises():
    llm = GroqChat(api_key="k", model="m", client=FakeGroqClient(fail=True))
    assert invoke_text(llm, "q") is None


def test_get_llm_returns_none_without_key_or_when_disabled(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert get_llm() is None
    monkeypatch.setenv("LLM_PROVIDER", "none")
    assert get_llm() is None


# ---------------------------------------------------------------- Ollama (HTTP mocked)
import json  # noqa: E402
import logging  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402

from agent.llm import OllamaChat, llm_preflight  # noqa: E402


def ollama_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_ollama_chat_sends_documented_payload_and_parses_reply():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "hello"}})

    llm = OllamaChat(model="llama3.1:8b", base_url="http://localhost:11434/", client=ollama_client(handler))
    assert llm.invoke("hi").content == "hello"
    body = seen["body"]
    assert seen["url"] == "http://localhost:11434/api/chat"
    assert body["model"] == "llama3.1:8b" and body["stream"] is False
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert body["options"]["num_ctx"] == 4096 and body["options"]["temperature"] == 0.0
    assert "format" not in body  # plain text unless JSON mode is requested


def test_ollama_json_mode_sets_format_json():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "{}"}})

    OllamaChat(client=ollama_client(handler)).invoke("q", json_mode=True)
    assert bodies[0]["format"] == "json"


def test_invoke_text_requests_json_mode_only_from_clients_that_support_it():
    calls = []

    class JsonLLM:
        supports_json_mode = True

        def invoke(self, prompt, json_mode=False):
            calls.append(json_mode)
            return SimpleNamespace(content="{}")

    class PlainLLM:  # e.g. Groq wrapper / test fakes: invoke(prompt) only
        def invoke(self, prompt):
            calls.append("plain")
            return SimpleNamespace(content="{}")

    assert invoke_text(JsonLLM(), "p", json_mode=True) == "{}"
    assert invoke_text(PlainLLM(), "p", json_mode=True) == "{}"
    assert calls == [True, "plain"]


def test_llm_failures_are_logged_not_silent(caplog):
    def handler(request):
        return httpx.Response(500, text="boom")

    llm = OllamaChat(client=ollama_client(handler))
    with caplog.at_level(logging.WARNING, logger="agent.llm"):
        assert invoke_text(llm, "q") is None
    assert "LLM call failed" in caplog.text


def test_get_llm_builds_ollama_from_environment(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    llm = get_llm()
    assert isinstance(llm, OllamaChat) and llm.base_url == "http://host.docker.internal:11434"


@pytest.mark.parametrize("tags,ready,fragment", [
    ({"models": [{"name": "llama3.1:8b"}]}, True, "ready"),
    ({"models": [{"name": "mistral:7b"}]}, False, "ollama pull llama3.1:8b"),
    ({"models": []}, False, "ollama pull"),
])
def test_preflight_checks_that_the_model_is_pulled(monkeypatch, tags, ready, fragment):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")
    ok, detail = llm_preflight(client=ollama_client(lambda r: httpx.Response(200, json=tags)))
    assert ok is ready and fragment in detail


def test_preflight_reports_unreachable_ollama(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    def refuse(request):
        raise httpx.ConnectError("refused")

    ok, detail = llm_preflight(client=ollama_client(refuse))
    assert ok is False and "ollama serve" in detail


def test_preflight_when_disabled(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    assert llm_preflight()[0] is False
