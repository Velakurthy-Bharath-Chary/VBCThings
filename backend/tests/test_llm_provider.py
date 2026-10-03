from types import SimpleNamespace

import pytest

from app.ai import llm


def test_generation_uses_groq_client(monkeypatch):
    captured = {}
    choice = SimpleNamespace(message=SimpleNamespace(content="Groq answer"))
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: captured.update(kwargs) or SimpleNamespace(choices=[choice])
            )
        )
    )
    monkeypatch.setattr(llm, "_client", lambda: client)
    assert llm.generate_answer("system", "question") == "Groq answer"
    assert captured["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "question"},
    ]


def test_stream_yields_groq_chunks(monkeypatch):
    chunks = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="one"))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="two"))]),
    ]
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_kwargs: iter(chunks))
        )
    )
    monkeypatch.setattr(llm, "_client", lambda: client)
    assert list(llm.generate_answer_stream("system", "question")) == ["one", "two"]


def test_empty_groq_response_returns_safe_error(monkeypatch):
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_kwargs: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=""))]
                )
            )
        )
    )
    monkeypatch.setattr(llm, "_client", lambda: client)
    with pytest.raises(RuntimeError, match="language model is currently unavailable"):
        llm.generate_answer("system", "question")
