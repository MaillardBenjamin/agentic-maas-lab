"""Real HTTP integration scenario against the Docker stack. No paid APIs."""
import concurrent.futures
import json
import os
import time
import uuid

import httpx

BASE = os.environ.get("API_URL", "http://api:8000")


def login(uid):
    r = httpx.post(BASE + "/api/demo/login/" + uid)
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def call(path, headers, body=None, status=200):
    r = httpx.request("POST" if body is not None else "GET", BASE + path, headers=headers, json=body, timeout=15)
    diagnostic = "Réponse audio masquée" if path.startswith("/api/voice/session") else r.text
    assert r.status_code == status, (path, r.status_code, diagnostic)
    return r.json()


def wait(oid, state, headers):
    for _ in range(60):
        value = call("/api/orders/" + oid, headers)
        if value["state"] == state:
            return value
        time.sleep(1)
    raise AssertionError(f"Commande {oid} non passée à {state}, état={value['state']}")


def run():
    lea, demo, clerk = login("lea"), login("demo"), login("clerk")
    q = call("/api/quotes", lea, {"traveler": "lea", "seller": "agency", "products": ["transport", "parking", "bike"], "travel_date": "2026-10-24"})
    assert q["total_cents"] == 1200
    payload = {"quote_id": q["id"], "idempotency_key": "smoke-" + uuid.uuid4().hex, "pause_before_issue": True}
    order = call("/api/orders", lea, payload)
    oid = order["id"]
    assert order["account_id"] == "abt-account-alize-lea"
    assert call("/api/orders", lea, payload)["id"] == oid
    call("/api/demo/orders/" + oid + "/pay", lea, {})
    call("/api/demo/orders/" + oid + "/pay", lea, {})
    value = wait(oid, "awaiting_resume", lea)
    assert value["payment_count"] == 1
    call("/api/demo/orders/" + oid + "/continue", lea, {})
    value = wait(oid, "fulfilled", lea)
    assert value["card"]["load_count"] == 1
    assert value["card"]["sdk"]["verified_read_after_write"] is True
    event = {"id": oid + "-x-1", "source": "urn:manufacturer:x", "type": "maas.validation.accepted.v1", "time": "2026-10-24T09:00:00Z", "data": {"order_id": oid, "passage_id": "passage-1"}}
    assert call("/api/events", demo, event)["accepted"]
    assert call("/api/events", demo, event)["duplicate"]
    other = {**event, "id": oid + "-y-1", "source": "urn:manufacturer:y"}
    assert call("/api/events", demo, other)["duplicate"]
    bike = {**event, "id": oid + "-bike-1", "source": "urn:partner:bike", "type": "maas.bike.ended.v1", "data": {"order_id": oid, "passage_id": "rental-1", "seconds": 600}}
    call("/api/events", demo, bike)
    call("/api/events", demo, {**bike, "data": {**bike["data"], "seconds": 601}}, 409)
    call("/api/events", demo, {**event, "data": {**event["data"], "passage_id": "contradiction"}}, 409)
    call("/api/orders/" + oid + "/refunds", clerk, {"amount_cents": 600, "reason": "Dépassement de la délégation", "idempotency_key": "refused-001"}, 403)
    refund = {"amount_cents": 200, "reason": "Régularisation parking fictive", "idempotency_key": "refund-" + uuid.uuid4().hex}
    # Two actual simultaneous HTTP requests, one persisted effect.
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: call("/api/orders/" + oid + "/refunds", clerk, refund), range(2)))
    assert results[0]["id"] == results[1]["id"]
    s = call("/api/orders/" + oid + "/statement", clerk)
    assert (s["refund_cents"], s["seller_commission_cents"], s["operators_cents"], s["bike_due_cents"], s["events_count"]) == (200, 50, 950, 300, 2)
    call("/api/orders/" + oid, login("adult"), status=403)
    call("/api/orders/" + oid + "/refunds", lea, refund, 403)
    found = call("/api/knowledge/search", lea, {"query": "contrats distribution"})
    assert any(x["id"] == "distribution-1" for x in found["sources"])
    print(json.dumps({"status": "passed", "order_id": oid, "checks": ["tarif étudiant", "commande idempotente", "paiement répété", "reprise Temporal", "émission unique", "doublon inter-fabricants", "facturation vélo", "refus OPA", "remboursements concurrents", "isolation voyageur", "sources FalkorDB"], "statement": s}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
