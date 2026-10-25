"""Real A2A/MCP + PostgreSQL/Temporal; explicit fixture or real local/cloud LLM."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import time
import uuid
import httpx
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from maas.api import log
from maas.db import Session
from maas.partners import PartnerRequest, prepare_operation
from maas.partner_grants import grant_for
from maas.security import USERS
from maas.ai import chat_backend

parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=["fixture", "ollama", "openai"])
args = parser.parse_args()
base = os.environ.get("API_URL", "http://api:8000")
fixture = args.mode == "fixture"
if not fixture and chat_backend() != ("ollama_local" if args.mode == "ollama" else "openai_via_agno"):
    raise SystemExit("Sélectionner explicitement le fournisseur demandé avant le test ; aucun achat ni appel modèle lancé.")
headers = {"Authorization": "Bearer " + httpx.post(base + "/api/demo/login/lea").json()["access_token"]}
demo = {"Authorization": "Bearer " + httpx.post(base + "/api/demo/login/demo").json()["access_token"]}
prefix = "partners-" + uuid.uuid4().hex


def call(path, body=None, auth=headers, expected=200):
    r = httpx.request("GET" if body is None else "POST", base + path, headers=auth, json=body, timeout=30)
    assert r.status_code == expected, (path, r.status_code, r.json().get("detail"))
    return r.json()


def new_order():
    quote = call("/api/quotes", {"traveler": "lea", "seller": "agency", "products": ["transport", "bike", "parking"]})
    order = call("/api/orders", {"quote_id": quote["id"], "idempotency_key": prefix + "-" + uuid.uuid4().hex[:8], "pause_before_issue": False})
    call("/api/demo/orders/" + order["id"] + "/pay", {})
    for _ in range(60):
        if call("/api/orders/" + order["id"])["state"] == "fulfilled":
            return order["id"]
        time.sleep(1)
    raise AssertionError("Titre non délivré")


async def start_fixture(op):
    client = await Client.connect(os.environ.get("TEMPORAL_ADDRESS", "temporal:7233"))
    try:
        await client.start_workflow("PartnerInteraction", {"operation_id": op["id"], "fixture": True}, id=op["id"], task_queue="maas-ticketing", id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
    except WorkflowAlreadyStartedError:
        pass


def prepare(oid, partner, action, seconds=None, key=None):
    body = {"partner": partner, "action": action, "confirmed": True, "idempotency_key": key or prefix + "-" + partner + "-" + action, "duration_seconds": seconds}
    if fixture:
        with Session.begin() as db:
            op = prepare_operation(db, oid, PartnerRequest(**body), USERS["lea"], log, test_only=True)
        asyncio.run(start_fixture(op))
    else:
        op = call("/api/orders/" + oid + "/partner-operations", body)
    return op, body


def wait(oid, op):
    for _ in range(360):
        data = call("/api/orders/" + oid + "/partners")
        value = next(x for x in data["operations"] if x["id"] == op["id"])
        if value["status"] in ("completed", "failed"):
            return value
        time.sleep(1)
    raise AssertionError("Opération partenaire non terminée : " + op["id"])


def run_action(oid, partner, action, seconds=None, key=None):
    started = time.monotonic()
    op, body = prepare(oid, partner, action, seconds, key)
    value = wait(oid, op)
    assert value["status"] == "completed", {"status": value["status"], "error": value.get("error"), "operation_id": op["id"]}
    assert value["effect_count"] == 1
    assert value["mode"] == ("fixture-no-llm" if fixture else "ollama_local" if args.mode == "ollama" else "openai_via_agno")
    assert {"mobility", partner}.issubset(value["evidence"]["a2a_agents"])
    assert {partner + "_availability", partner + "_apply"}.issubset(value["evidence"]["mcp_tools"])
    replay, _ = prepare(oid, partner, action, seconds, body["idempotency_key"])
    assert replay["id"] == op["id"]
    return {"operation_id": op["id"], "partner": partner, "action": action, "mode": value["mode"], "model": value["model"], "state": value["result"]["booking"]["state"], "evidence": value["evidence"], "elapsed_ms": round((time.monotonic() - started) * 1000)}


oid = new_order()
before_budget = call("/api/budget")["reserved_cents"]
initial_stock = call("/api/orders/" + oid + "/partners")["availability"]
results = []
for partner in ("bike", "parking"):
    for action in ("reserve", "start", "finish"):
        result = run_action(oid, partner, action, 600 if partner == "bike" and action == "finish" else None)
        results.append(result)
        print(json.dumps({"progress": partner + ":" + action, "status": "passed", "mode": result["mode"], "elapsed_ms": result["elapsed_ms"]}), flush=True)

state = call("/api/orders/" + oid + "/partners")
assert state["availability"] == initial_stock
assert len(state["bookings"]) == 2 and all(x["state"] == "completed" for x in state["bookings"])
statement = call("/api/orders/" + oid + "/statement")
assert statement["bike_due_cents"] == 300 and statement["events_count"] == 2
order = call("/api/orders/" + oid)
assert order["payment_count"] == 1 and order["card"]["load_count"] == 1
for event in order["events"]:
    body = {key: event[key] for key in ("specversion", "id", "source", "type", "time", "data")}
    assert call("/api/events", body, auth=demo)["duplicate"]
assert call("/api/orders/" + oid + "/statement")["bike_due_cents"] == 300
last = state["operations"][0]
scope = {"Authorization": "Bearer " + grant_for(last)}
other = "parking" if last["partner"] == "bike" else "bike"
call("/api/partner-tools/" + other + "/availability", auth=scope, expected=403)
call("/api/partner-tools/bike/apply", {}, expected=401)
adult = {"Authorization": "Bearer " + httpx.post(base + "/api/demo/login/adult").json()["access_token"]}
call("/api/orders/" + oid + "/partners", auth=adult, expected=403)
call("/api/orders/" + oid + "/partner-operations", {"partner": "bike", "action": "reserve", "confirmed": False, "idempotency_key": prefix}, expected=422)
if args.mode != "openai":
    assert call("/api/budget")["reserved_cents"] == before_budget
report = {"status": "passed", "mode": args.mode, "order_id": oid, "operations": results, "stock_restored": True, "duplicate_events_without_second_charge": True, "unscoped_tools_refused": True, "cross_traveler_refused": True, "confirmation_required": True, "payment_count": 1, "card_load_count": 1, "statement": statement}
Path("/proofs/partner-" + args.mode + "-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False, indent=2))
