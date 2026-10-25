"""Shared runtime policy: local inference never silently switches to a cloud provider."""
import os
from urllib.parse import urlparse


def ollama_target():
    host = os.environ.get("OLLAMA_HOST", "http://host.docker.internal:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "qwen3:14b")
    parsed = urlparse(host)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1", "host.docker.internal", "ollama"} or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError("OLLAMA_HOST doit désigner le serveur local de démonstration")
    if not model or "cloud" in model.lower() or "/" in model or len(model) > 120:
        raise ValueError("Modèle Ollama local requis, sans délégation cloud")
    return host, model


def chat_backend():
    if os.environ.get("AI_ENABLED") != "true":
        return None
    mode = os.environ.get("AGENT_MODE", "disabled")
    if mode == "ollama":
        ollama_target()
        return "ollama_local"
    if mode == "openai" and os.environ.get("OPENAI_API_KEY"):
        return "openai_via_agno"
    return None
