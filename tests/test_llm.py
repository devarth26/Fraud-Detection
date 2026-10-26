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
