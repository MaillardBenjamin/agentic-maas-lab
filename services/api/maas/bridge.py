"""Bridge sandbox only. No retry of an ambiguous creation request."""
import hashlib
import hmac
import os
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import httpx

BASE = "https://api.bridgeapi.io/v3/payment/payment-requests"
LINKS = "https://api.bridgeapi.io/v3/payment/payment-links"


class BridgeRequestRejected(Exception):
    def __init__(self, status_code, code):
        self.status_code, self.code = status_code, code
        super().__init__("Bridge a refusé la création sans paiement")


def configured():
    return os.environ.get("BRIDGE_ENABLED") == "true" and os.environ.get("BRIDGE_CLIENT_ID", "").startswith("sandbox_id_") and os.environ.get("BRIDGE_CLIENT_SECRET", "").startswith("sandbox_secret_")


def headers():
    if not configured():
        raise ValueError("Bridge sandbox non configuré ou désactivé")
    return {"Client-Id": os.environ["BRIDGE_CLIENT_ID"], "Client-Secret": os.environ["BRIDGE_CLIENT_SECRET"], "Bridge-Version": "2025-01-15", "accept": "application/json"}


def payment_payload(order):
    flow = os.environ.get("BRIDGE_FLOW", "payment_link")
    if flow not in ("payment_request", "payment_link"):
        raise ValueError("Parcours Bridge inconnu")
    iban = os.environ.get("BRIDGE_BENEFICIARY_IBAN", "")
    default_beneficiary = flow == "payment_link" and os.environ.get("BRIDGE_BENEFICIARY_MODE", "default") == "default"
    if not iban and not default_beneficiary:
        raise ValueError("IBAN bénéficiaire de test Bridge requis")
    payload = {"callback_url": os.environ.get("BRIDGE_CALLBACK_URL", "http://localhost:5190"), "client_reference": order["id"], "user": {"first_name": "Lea", "last_name": "Demo", "external_reference": "maas-fictive-lea"}, "transactions": [{"amount": float(Decimal(order["quote"]["total_cents"]) / 100), "currency": "EUR", "label": "MaaS fictif sandbox", "client_reference": order["id"]}]}
    if order.get("channel") == "automate" and flow == "payment_link":
        payload.pop("callback_url")  # A phone must not redirect to localhost on the kiosk.
    if order.get("traveler") == "adult":
        payload["user"] = {"first_name": "Alex", "last_name": "Demo", "external_reference": "maas-fictive-adult"}
    if not default_beneficiary:
        payload["transactions"][0]["beneficiary"] = {"company_name": "Alize demonstration", "iban": iban}
    if flow == "payment_link":
        payload["provider_id"] = 574
        payload["expired_date"] = (datetime.now(timezone.utc) + (timedelta(minutes=10) if order.get("channel") == "automate" else timedelta(hours=1))).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        payload["bank_id"] = 574
    return payload


def create_payment(payload):
    link = "provider_id" in payload
    result = httpx.post(LINKS if link else BASE, headers=headers(), json=payload, timeout=15)
    if result.status_code in (400, 401, 403, 404, 422):
        try:
            code = result.json().get("errors", [{}])[0].get("code", "rejected")
        except (ValueError, IndexError, AttributeError):
            code = "rejected"
        code = code if isinstance(code, str) and re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", code) else "rejected"
        raise BridgeRequestRejected(result.status_code, code)
    result.raise_for_status()
    value = result.json()
    if not value.get("id") or not str(value.get("url", "")).startswith("https://pay.bridgeapi.io/"):
        raise ValueError("Réponse Bridge inattendue")
    return {"id": value["id"], "url": value["url"], "resource_type": "payment_link" if link else "payment_request", "expires_at": payload.get("expired_date")}


def read_payment(request_id, resource_type="payment_request"):
    if not request_id.isalnum() and not all(c.isalnum() or c == "-" for c in request_id):
        raise ValueError("Identifiant Bridge invalide")
    with httpx.Client(timeout=15) as client:
        if resource_type == "payment_link":
            link_response = client.get(LINKS + "/" + request_id, headers=headers())
            link_response.raise_for_status()
            link = link_response.json()
            requests = client.get(BASE, params={"payment_link_id": request_id, "limit": 100}, headers=headers())
            requests.raise_for_status()
            values = requests.json().get("resources", [])
            if not values:
                return {"status": "CREA", "client_reference": link.get("client_reference"), "transactions": link.get("transactions", []), "link_status": link.get("status"), "payment_link_id": request_id}
            if len(values) != 1:
                raise ValueError("Plusieurs tentatives bancaires : rapprochement requis")
            value = values[0]
            if value.get("client_reference") is None:
                value["client_reference"] = link.get("client_reference")
            value["link_status"] = link.get("status")
            value["payment_link_id"] = request_id
            return value
        result = client.get(BASE + "/" + request_id, headers=headers())
        result.raise_for_status()
        return result.json()


def settled_for_order(value, order):
    transactions = value.get("transactions", [])
    if value.get("status") != "ACSC" or value.get("client_reference") != order["id"] or len(transactions) != 1:
        return False
    tx = transactions[0]
    try:
        amount = Decimal(str(tx.get("amount", -1)))
        return amount.is_finite() and tx.get("client_reference", order["id"]) == order["id"] and tx.get("currency") == "EUR" and tx.get("status") == "ACSC" and amount * 100 == order["quote"]["total_cents"]
    except InvalidOperation:
        return False


def notification_matches(order, content):
    payment = order.get("bridge", {})
    if payment.get("resource_type", "payment_request") == "payment_link":
        return bool(payment.get("id")) and content.get("payment_link_id") == payment["id"]
    return bool(payment.get("id")) and content.get("payment_request_id") == payment["id"]


def verify_signature(raw, signature, secret):
    if not secret:
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    signatures = [part.strip().partition("=") for part in signature.split(",")]
    return any(scheme == "v1" and hmac.compare_digest(value.lower(), expected) for scheme, _, value in signatures)
