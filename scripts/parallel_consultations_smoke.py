"""Verify actual overlapping A2A consultations with the local model and live traces."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
from pathlib import Path
import time

import httpx
from maas.ai import chat_backend


def run():
    if chat_backend() != "ollama_local":
        raise SystemExit("Ollama local requis pour ce test ; aucun appel modèle lancé.")
    base = os.environ.get("API_URL", "http://api:8000")
    with httpx.Client(base_url=base, timeout=610) as client:
        headers = {"Authorization": "Bearer " + client.post("/api/demo/login/lea").json()["access_token"]}
        orders = client.get("/api/orders", headers=headers).json()
        providers = {"transport", "bike", "parking"}
        selected = next((o for o in orders if providers.issubset({l.get("provider", l["product"]) for l in o["quote"]["lines"]})), None)
        assert selected, "Une commande de démonstration transport, vélo et parking est requise"
        partner_path = "/api/orders/" + selected["id"] + "/partners"
        before = client.get(partner_path, headers=headers).json()
        cursor = client.get("/api/agent-activity", headers=headers).json()["cursor"]
        events = []
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=1) as pool:
            reply = pool.submit(client.post, "/api/chat", headers=headers, json={"agent": "clearing", "order_id": selected["id"], "message": "Explique les commissions et la répartition par fournisseur de ma commande. Consulte Transport, Vélo et Parking."})
            deadline = time.monotonic() + 600
            while not reply.done() and time.monotonic() < deadline:
                feed = client.get("/api/agent-activity?after=" + str(cursor), headers=headers).json()
                cursor = feed["cursor"]
                events.extend(feed["events"])
                time.sleep(.5)
            response = reply.result()
            events.extend(client.get("/api/agent-activity?after=" + str(cursor), headers=headers).json()["events"])
            if response.is_error:
                path = Path("/evidence/parallel-consultations-failed.json")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"status": "failed", "http_status": response.status_code, "detail": response.json().get("detail"), "events": events}, ensure_ascii=False, indent=2))
            response.raise_for_status()
            answer = response.json()
        assert answer["mode"] == "ollama_local"
        assert providers.issubset(answer["evidence"]["a2a_agents"]), answer
        assert "read_statement" in answer["evidence"]["mcp_tools"], answer
        assert not {"bike_apply", "parking_apply"} & set(answer["evidence"]["mcp_tools"])
        events = [e for e in events if e["run_id"] == answer["activity_run_id"]]
        spans = {}
        for provider in sorted(providers):
            first = next(e for e in events if e["protocol"] == "A2A" and e["source"] == "clearing" and e["target"] == provider and e["state"] == "started")
            end = next(e for e in events if e["span_id"] == first["span_id"] and e["state"] == "completed")
            spans[provider] = {"started": first["at"], "completed": end["at"], "duration_ms": end["duration_ms"]}
        starts = [datetime.fromisoformat(s["started"]) for s in spans.values()]
        ends = [datetime.fromisoformat(s["completed"]) for s in spans.values()]
        assert max(starts) < min(ends), ("Les consultations ne se chevauchent pas", spans)
        assert before == client.get(partner_path, headers=headers).json(), "Une consultation a modifié les stocks ou opérations"
        report = {"status": "passed", "mode": answer["mode"], "model": answer["model"], "provider": answer["provider"], "all_three_started_before_first_completed": True, "launch_spread_ms": round((max(starts) - min(starts)).total_seconds() * 1000), "elapsed_seconds": round(time.monotonic() - started, 2), "supplier_spans": spans, "business_state_unchanged": True, "evidence": answer["evidence"], "events": events, "answer": answer["text"]}
        path = Path("/evidence/parallel-consultations-ollama.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps({k: v for k, v in report.items() if k not in ("events", "answer")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    run()
