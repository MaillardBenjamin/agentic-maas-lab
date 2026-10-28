"""Explicit live-model test. May consume OpenAI tokens only in openai mode."""
import argparse
import json
import os
import time
import httpx

parser = argparse.ArgumentParser()
parser.add_argument("provider", choices=["openai", "ollama"])
parser.add_argument("--agent", choices=["tariffs", "conversation"], default="conversation")
args = parser.parse_args()
base = os.environ.get("API_URL", "http://api:8000")
with httpx.Client(timeout=610) as client:
    login = client.post(base + "/api/demo/login/lea")
    login.raise_for_status()
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    before = client.get(base + "/api/budget", headers=headers).json()["reserved_cents"]
    started = time.monotonic()
    response = client.post(base + "/api/chat", headers=headers, json={"agent": args.agent, "message": "Explique en français le prix du titre transport pour un étudiant dont le droit est valide. Consulte le catalogue et la source étudiant via tes outils, puis cite la source. Réponse courte."})
    elapsed = round((time.monotonic() - started) * 1000)
    if response.status_code != 200:
        raise SystemExit(json.dumps({"status": "failed", "provider": args.provider, "http_status": response.status_code, "detail": response.json().get("detail"), "elapsed_ms": elapsed}))
    value = response.json()
    expected = "ollama_local" if args.provider == "ollama" else "openai_via_agno"
    assert value["mode"] == expected, "Unexpected inference provider"
    assert "SIMULATION DE MODÈLE" not in value["text"]
    assert "read_provider_context" in value["evidence"]["mcp_tools"], value
    assert "transport" in value["evidence"]["a2a_agents"], value
    assert "tariff-1" in value["text"] and "7" in value["text"], value
    if args.agent == "conversation":
        assert "tariffs" in value["evidence"]["a2a_agents"], value
    after = client.get(base + "/api/budget", headers=headers).json()["reserved_cents"]
    assert after - before == (0 if args.provider == "ollama" else 100)
    print(json.dumps({"status": "passed", "provider": value["provider"], "mode": value["mode"], "model": value["model"], "agent": args.agent, "evidence": value["evidence"], "elapsed_ms": elapsed, "reservation_delta_cents": after - before, "answer": value["text"]}, ensure_ascii=False, indent=2))
