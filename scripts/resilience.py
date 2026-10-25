"""Phased test: stop/restart the actual Worker between prepare and check."""
import json
import os
import sys
import uuid
import httpx
from smoke import call, login, wait

path = "/proofs/resilience.json"
phase = sys.argv[1]
headers = login("lea")
if phase == "prepare":
    q = call("/api/quotes", headers, {"traveler": "lea", "products": ["transport"], "seller": "agency"})
    order = call("/api/orders", headers, {"quote_id": q["id"], "idempotency_key": "crash-" + uuid.uuid4().hex, "pause_before_issue": True})
    call("/api/demo/orders/" + order["id"] + "/pay", headers, {})
    wait(order["id"], "awaiting_resume", headers)
    with open(path, "w") as f:
        json.dump({"order_id": order["id"]}, f)
    print({"phase": phase, "order_id": order["id"], "state": "awaiting_resume"})
elif phase == "signal-stopped":
    oid = json.load(open(path))["order_id"]
    # Configure a committed card load whose first response is lost. Simulator has its own DB.
    r = httpx.post("http://simulator:8001/faults/lose-response", json={"operation_id": oid}, headers={"X-Service-Token": os.environ["SERVICE_TOKEN"]})
    r.raise_for_status()
    call("/api/demo/orders/" + oid + "/continue", headers, {})
    assert call("/api/orders/" + oid, headers)["state"] == "awaiting_resume"
    print({"phase": phase, "signal": "persisted while Worker absent"})
elif phase == "check":
    oid = json.load(open(path))["order_id"]
    order = wait(oid, "fulfilled", headers)
    assert order["payment_count"] == 1
    assert order["card"]["load_count"] == 1
    assert order["card"]["reconciled"] is True
    print({"status": "passed", "actual_worker_restart": True, "committed_response_lost": True, "payment_count": 1, "card_load_count": 1, "order_id": oid})
