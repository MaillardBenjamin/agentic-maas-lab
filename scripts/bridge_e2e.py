"""Explicit sandbox payment scenario; consent is completed in Bridge Demo Bank UI."""
import argparse
import json
import os
from pathlib import Path
import time
import uuid
import httpx

parser = argparse.ArgumentParser()
parser.add_argument("phase", choices=["prepare", "status", "verify"])
parser.add_argument("--case", choices=["success", "rejected"], default="success")
parser.add_argument("--new", action="store_true", help="Archive le scénario précédent sans modifier sa commande, puis crée un nouvel essai sandbox")
args = parser.parse_args()
base = os.environ.get("API_URL", "http://api:8000")
path = Path("/proofs/bridge-e2e-" + args.case + ".json")

with httpx.Client(timeout=25) as client:
    login = client.post(base + "/api/demo/login/lea")
    login.raise_for_status()
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}

    def call(route, body=None, expected=200):
        response = client.request("GET" if body is None else "POST", base + route, headers=headers, json=body)
        if response.status_code != expected:
            detail = response.json().get("detail", "Réponse inattendue")
            raise RuntimeError(json.dumps({"route": route, "http_status": response.status_code, "detail": detail}, ensure_ascii=False))
        return response.json()

    if args.phase == "prepare":
        if path.exists():
            if not args.new:
                raise SystemExit("Scénario déjà préparé : utiliser status ou verify ; --new archive cet essai avant un nouvel achat fictif.")
            previous = json.loads(path.read_text())
            previous_order = call("/api/orders/" + previous["order_id"])
            if previous_order["payment_count"]:
                raise SystemExit("Scénario déjà payé : conserver sa preuve et utiliser un autre cas de test.")
            archived = path.with_name(path.stem + "-" + previous["order_id"] + ".json")
            path.rename(archived)
        quote = call("/api/quotes", {"traveler": "lea", "seller": "agency", "products": ["transport", "parking", "bike"], "travel_date": "2026-10-24"})
        assert quote["total_cents"] == 1200
        purchase = {"quote_id": quote["id"], "idempotency_key": "bridge-e2e-" + uuid.uuid4().hex, "channel": "web", "payment_mode": "bridge_sandbox", "pause_before_issue": False}
        order = call("/api/orders", purchase)
        state = {"order_id": order["id"], "purchase": purchase, "amount_cents": 1200, "case": args.case}
        path.write_text(json.dumps(state, indent=2))
        created = call("/api/orders/" + order["id"] + "/bridge", {})
        assert call("/api/orders/" + order["id"] + "/bridge", {})["id"] == created["id"]
        state["bridge"] = created
        path.write_text(json.dumps(state, indent=2))
        status = call("/api/orders/" + order["id"] + "/bridge/status", {})
        unpaid = call("/api/orders/" + order["id"])
        assert unpaid["payment_count"] == 0 and "card" not in unpaid
        print(json.dumps({"phase": "prepared", "order_id": order["id"], "bank_payment_id": created["id"], "consent_url": created["url"], "amount_cents": 1200, "provider_status": status["provider_status"], "no_issuance_before_bank_confirmation": True}, ensure_ascii=False, indent=2))
    else:
        state = json.loads(path.read_text())
        oid = state["order_id"]
        bank = call("/api/orders/" + oid + "/bridge/status", {})
        if args.phase == "status":
            order = call("/api/orders/" + oid)
            print(json.dumps({"bank": bank, "order_state": order["state"], "payment_count": order["payment_count"]}))
        elif args.case == "rejected":
            order = call("/api/orders/" + oid)
            assert bank["provider_status"] == "RJCT" and bank["settled"] is False
            assert order["payment_count"] == 0 and "card" not in order
            print(json.dumps({"status": "passed", "case": "rejected", "bank": bank, "no_payment_or_issuance": True}))
        else:
            assert bank["provider_status"] == "ACSC" and bank["settled"] is True, bank
            for _ in range(45):
                order = call("/api/orders/" + oid)
                if order["state"] == "fulfilled":
                    break
                time.sleep(1)
            assert order["state"] == "fulfilled", order["state"]
            assert order["payment_count"] == 1
            assert order["card"]["load_count"] == 1 and order["card"]["sdk"]["verified_read_after_write"]
            # Replay provider polling after workflow completion: no second signal failure/effect.
            assert call("/api/orders/" + oid + "/bridge/status", {})["settled"]
            assert call("/api/orders", state["purchase"])["id"] == oid
            call("/api/demo/orders/" + oid + "/pay", {}, expected=409)
            final = call("/api/orders/" + oid)
            assert final["payment_count"] == 1 and final["card"]["load_count"] == 1
            statement = call("/api/orders/" + oid + "/statement")
            assert (statement["prepaid_cents"], statement["seller_commission_cents"], statement["operators_cents"]) == (1200, 60, 1140)
            report = {"status": "passed", "order_id": oid, "bank_payment_id": state["bridge"]["id"], "bank_request_id": bank["payment_request_id"], "bank_status": "ACSC", "amount_cents": 1200, "order_state": final["state"], "payment_count": 1, "card_load_count": 1, "keyple_read_after_write": True, "replayed_polling_without_second_effect": True, "statement": statement}
            path.with_name(path.stem + "-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print(json.dumps(report, ensure_ascii=False, indent=2))
