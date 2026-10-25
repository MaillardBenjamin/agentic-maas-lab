"""Negative paths against real API/OPA services, with fictive identities only."""
from smoke import call, login
from maas.security import USERS, token
import httpx
import sys

lea, clerk = login("lea"), login("clerk")
orders = call("/api/orders", lea)
oid = next(o["id"] for o in orders if o["state"] == "fulfilled")
if "opa-down" in sys.argv:
    before = call("/api/orders/" + oid + "/statement", clerk)["refund_cents"]
    call("/api/orders/" + oid + "/refunds", clerk, {"amount_cents": 1, "reason": "Refus pendant panne OPA", "idempotency_key": "opa-down-no-effect"}, 503)
    assert call("/api/orders/" + oid + "/statement", clerk)["refund_cents"] == before
    print({"status": "passed", "opa_outage": "sensitive operation refused, no financial effect"})
    raise SystemExit(0)
q = call("/api/quotes", lea, {"traveler": "lea", "products": ["transport"], "seller": "agency"})
before = call("/api/budget", lea)
integrations = call("/api/integrations", lea)
bank = any(i["name"] == "Bridge" and i["mode"] == "configured" for i in integrations)
if not bank:
    call("/api/orders", lea, {"quote_id": q["id"], "idempotency_key": "disabled-bank-" + q["id"], "payment_mode": "bridge_sandbox"}, 503)
cloud = any(i["name"] == "OpenAI" and i["mode"] == "configured" for i in integrations)
local = any(i["name"] == "Ollama" and i["mode"] == "configured" for i in integrations)
if not cloud and not local:
    call("/api/chat", lea, {"message": "Explique le tarif"}, 503)
if not cloud:
    call("/api/voice/session", lea, {}, 503)
assert call("/api/budget", lea)["reserved_cents"] == before["reserved_cents"]
foreign = {"Authorization": "Bearer " + token({**USERS["clerk"], "org": "other-operator"})}
call("/api/orders/" + oid, foreign, status=403)
call("/api/orders/" + oid + "/refunds", foreign, {"amount_cents": 100, "reason": "Accès hors organisation", "idempotency_key": "cross-org-refund"}, 403)
call("/api/webhooks/bridge", {}, {"content": {"payment_request_id": "forged"}}, 401)
call("/api/orders", {}, status=401)
print({"status": "passed", "checks": ["no cloud budget debit", "cross-organization read", "cross-organization refund", "unsigned webhook", "missing JWT"], "disabled_bank_checked": not bank, "disabled_chat_checked": not cloud and not local, "disabled_voice_checked": not cloud})
