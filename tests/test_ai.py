import pytest
from maas.ai import chat_backend, ollama_target


def test_local_backend_requires_no_openai_key(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("AGENT_MODE", "ollama")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert chat_backend() == "ollama_local"


def test_global_disable_wins(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.setenv("AGENT_MODE", "ollama")
    assert chat_backend() is None


def test_missing_cloud_key_never_falls_back_to_local(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("AGENT_MODE", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert chat_backend() is None


@pytest.mark.parametrize("host", ["https://ollama.com", "http://example.com:11434", "http://localhost:11434/proxy", "http://user:password@localhost:11434", "http://localhost:11434?target=cloud"])
def test_nonlocal_ollama_endpoint_refused(monkeypatch, host):
    monkeypatch.setenv("OLLAMA_HOST", host)
    with pytest.raises(ValueError):
        ollama_target()


@pytest.mark.parametrize("model", ["gpt-oss:120b-cloud", "gpt-oss:120b:cloud", ""])
def test_cloud_model_refused_in_local_mode(monkeypatch, model):
    monkeypatch.setenv("OLLAMA_MODEL", model)
    with pytest.raises(ValueError):
        ollama_target()
