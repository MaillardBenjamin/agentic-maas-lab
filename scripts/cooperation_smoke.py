"""Organization cooperation over real A2A/MCP. Fixture and live evidence are distinct."""
import argparse
import json
import os
import re
from pathlib import Path
import time
import uuid

import httpx
from maas.ai import chat_backend
from maas.organizations import sign_scope
from maas.security import USERS

parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=["fixture", "ollama", "openai"])
parser.add_argument("--only", choices=["all", "support"], default="all")
args = parser.parse_args()
if args.mode != "fixture":
    assert chat_backend() == ("ollama_local" if args.mode == "ollama" else "openai_via_agno"), "Provider mismatch; no model request sent"
base = os.environ.get("API_URL", "http://api:8000")
results = []
with httpx.Client(timeout=610) as client:
    headers = {"Authorization": "Bearer " + client.post(base + "/api/demo/login/lea").json()["access_token"]}
    before = client.get(base + "/api/orders", headers=headers).json()

    def ask(question, expected, agent="conversation", order_id=None):
        started = time.monotonic()
        if args.mode == "fixture":
            selected = next((o for o in before if o["id"] == order_id), None)
            context = sign_scope("maas-coordination", USERS["lea"], traveler="lea", seller="app", order_id=order_id, providers=[l.get("provider", l["product"]) for l in selected["quote"]["lines"]] if selected else [])
            rid = str(uuid.uuid4())
            body = {"jsonrpc": "2.0", "id": rid, "method": "message/send", "params": {"message": {"messageId": rid, "role": "user", "parts": [{"kind": "text", "text": question}]}}}
            response = client.post("http://agent-fixture:8002/a2a/agents/" + agent + "/v1/message:send", headers={**headers, "X-MaaS-Coordination": context}, json=body)
            response.raise_for_status()
            task = response.json()["result"]
            assert task["status"]["state"] == "completed", task
            text = str(task)
            evidence = {"a2a_agents": response.headers.get("X-MaaS-A2A-Agents", "").split(","), "mcp_tools": response.headers.get("X-MaaS-MCP-Tools", "").split(",")}
            proposal = response.headers.get("X-MaaS-Proposal-ID")
            assert "SIMULATION DE MODÈLE" in text
        else:
            response = client.post(base + "/api/chat", headers=headers, json={"message": question, "agent": agent, "order_id": order_id})
            response.raise_for_status()
            data = response.json()
            evidence, text, proposal = data["evidence"], data["text"], data.get("proposal")
            assert "SIMULATION DE MODÈLE" not in text
        assert set(expected).issubset(evidence["a2a_agents"]), (question, evidence, text)
        assert "read_provider_context" in evidence["mcp_tools"], (evidence, text)
        assert not re.search(r"\b(?:300|500|700|1000|1200)\s*(?:€|euros?)", text), ("Centimes présentés comme euros", text)
        assert not {"bike_apply", "parking_apply"} & set(evidence["mcp_tools"]), evidence
        result = {"question": question, "evidence": evidence, "elapsed_seconds": round(time.monotonic() - started, 2), "answer": text}
        results.append(result)
        partial = Path("/evidence/cooperation-" + args.mode + ".json")
        partial.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(json.dumps({"status": "running", "mode": args.mode, "cases": results}, ensure_ascii=False, indent=2))
        print(json.dumps({k: v for k, v in result.items() if k != "answer"}, ensure_ascii=False), flush=True)
        return proposal, text

    if args.only == "all":
        _, answer = ask("Peux-tu me donner le tarif du parking ?", ["tariffs", "parking"])
        assert "parking-1" in answer and re.search(r"\b5(?:[,.]0{1,2})?\s*(?:€|euros?)", answer), answer
        assert not re.search(r"\b500\s*(?:€|euros?)", answer), answer
        ask("Y a-t-il une place disponible au parking ?", ["mobility", "parking"])
        proposal, _ = ask("Prépare une proposition transport, parking et vélo pour le 2026-10-29.", ["mobility", "transport", "parking", "bike"])
        assert proposal, "No reviewable proposal was produced"
        if isinstance(proposal, dict):
            assert proposal["total_cents"] == 1200 and proposal["seller"] == "app" and proposal["traveler"] == "lea", proposal
            assert proposal["travel_date"] == "2026-10-29"
    selected = next((o for o in before if any(l["product"] == "parking" for l in o["quote"]["lines"])), None)
    assert selected, "A saved demo order with parking is required for the SAV and clearing checks"
    ask("Le parking a refusé mon accès. Vérifie le dossier avec son organisation.", ["sav", "parking"], order_id=selected["id"])
    ask("Explique les commissions et la répartition par fournisseur de ma commande.", ["clearing", *[l.get("provider", l["product"]) for l in selected["quote"]["lines"]]], order_id=selected["id"])
    after = client.get(base + "/api/orders", headers=headers).json()
    assert {o["id"] for o in before} == {o["id"] for o in after}, "Consultations created a purchase"
    assert {o["id"]: o["state"] for o in before} == {o["id"]: o["state"] for o in after}, "Consultations changed order state"

output = {"status": "passed", "mode": args.mode, "model_simulated": args.mode == "fixture", "purchase_created": False, "cases": results}
path = Path("/evidence/cooperation-" + args.mode + ".json")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
print(json.dumps({"status": "passed", "mode": args.mode, "cases": len(results), "evidence": str(path)}, ensure_ascii=False))
