"""Inspect the latest QR kiosk order. Never confirms a payment on the client's behalf."""
import json
from pathlib import Path
import httpx

with httpx.Client(base_url="http://api:8000", timeout=30) as client:
    login = client.post("/api/demo/login/lea"); login.raise_for_status()
    auth = {"Authorization": "Bearer " + login.json()["access_token"]}
    response = client.get("/api/orders", headers=auth); response.raise_for_status()
    orders = response.json()
    order = next(o for o in orders if o.get("channel") == "automate" and o.get("payment_mode") == "bridge_sandbox")
    oid = order["id"]
    repeated = client.post(f"/api/orders/{oid}/bridge", headers=auth, json={})
    if not order["payment_count"]:
        repeated.raise_for_status()
        assert repeated.json()["id"] == order["bridge"]["id"]
        refused = client.post(f"/api/demo/orders/{oid}/pay", headers=auth, json={})
        assert refused.status_code == 409
        assert "card" not in order
    else:
        assert order["state"] == "fulfilled" and order["payment_count"] == 1
        assert order["bridge"]["provider_status"] == "ACSC"
        assert order["card"]["load_count"] == 1
        assert order["card"]["sdk"]["verified_read_after_write"] is True
    protected = client.post(f"/internal/orders/{oid}/bridge/status", json={})
    assert protected.status_code in (401, 403)
    evidence = {"order_id": oid, "channel": order["channel"], "amount_cents": order["quote"]["total_cents"], "state": order["state"], "payment_count": order["payment_count"], "bridge": {k: order["bridge"].get(k) for k in ("id", "provider_status", "link_status", "expires_at", "checked_at")}, "card": order.get("card"), "internal_endpoint_protected": True}
    Path("/proofs/kiosk-qr-2026-10-25.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))
