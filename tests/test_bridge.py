import hashlib
import hmac
import pytest
from maas.bridge import configured, payment_payload, settled_for_order, verify_signature

ORDER = {"id": "order-demo", "quote": {"total_cents": 1200}}


def test_live_credentials_refused(monkeypatch):
    monkeypatch.setenv("BRIDGE_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_CLIENT_ID", "live-id")
    monkeypatch.setenv("BRIDGE_CLIENT_SECRET", "live-secret")
    assert not configured()


def test_test_beneficiary_required(monkeypatch):
    monkeypatch.setenv("BRIDGE_FLOW", "payment_request")
    monkeypatch.delenv("BRIDGE_BENEFICIARY_IBAN", raising=False)
    with pytest.raises(ValueError):
        payment_payload(ORDER)


def test_payment_link_uses_default_beneficiary_and_demo_bank(monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setenv("BRIDGE_FLOW", "payment_link")
    monkeypatch.setenv("BRIDGE_BENEFICIARY_MODE", "default")
    monkeypatch.delenv("BRIDGE_BENEFICIARY_IBAN", raising=False)
    payload = payment_payload(ORDER)
    assert payload["provider_id"] == 574
    assert "beneficiary" not in payload["transactions"][0]
    assert payload["transactions"][0]["amount"] == 12
    seconds = (datetime.fromisoformat(payload["expired_date"].replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds()
    assert 3500 < seconds <= 3600


def test_transaction_reference_must_match():
    value = {"status": "ACSC", "client_reference": ORDER["id"], "transactions": [{"status": "ACSC", "client_reference": "another", "amount": 12, "currency": "EUR"}]}
    assert not settled_for_order(value, ORDER)


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "invalid", None])
def test_invalid_provider_amount_never_unlocks(amount):
    value = {"status": "ACSC", "client_reference": ORDER["id"], "transactions": [{"status": "ACSC", "amount": amount, "currency": "EUR"}]}
    assert not settled_for_order(value, ORDER)


def test_webhook_routes_payment_link_and_request_separately():
    from maas.bridge import notification_matches
    order = {"bridge": {"id": "link-id", "resource_type": "payment_link"}}
    assert notification_matches(order, {"payment_link_id": "link-id", "payment_request_id": "request-id"})
    assert not notification_matches(order, {"payment_request_id": "link-id"})
    assert not notification_matches(order, {"payment_link_id": "other"})
    assert notification_matches({"bridge": {"id": "request-id"}}, {"payment_request_id": "request-id"})
    assert not notification_matches({}, {})


@pytest.mark.parametrize("count", [0, 1, 2])
def test_link_completion_is_not_bank_settlement(monkeypatch, count):
    import httpx
    from maas import bridge
    monkeypatch.setattr(bridge, "headers", lambda: {})
    payment = {"id": "bank-request", "status": "PDNG", "transactions": [{"status": "PDNG", "currency": "EUR", "amount": 12}]}
    def respond(request):
        if "/payment-links/" in str(request.url):
            return httpx.Response(200, json={"id": "link-demo", "status": "completed", "client_reference": ORDER["id"], "transactions": [{"amount": 12, "currency": "EUR"}]})
        assert request.url.params["payment_link_id"] == "link-demo"
        return httpx.Response(200, json={"resources": [payment] * count})
    original_client = httpx.Client
    monkeypatch.setattr(bridge.httpx, "Client", lambda **kw: original_client(transport=httpx.MockTransport(respond), **kw))
    if count == 2:
        with pytest.raises(ValueError, match="Plusieurs tentatives"):
            bridge.read_payment("link-demo", "payment_link")
    else:
        value = bridge.read_payment("link-demo", "payment_link")
        assert not settled_for_order(value, ORDER)
        if count == 1:
            assert value["id"] == "bank-request" and value["client_reference"] == ORDER["id"]


def test_raw_body_signature_and_rotation():
    raw = b'{"type":"payment.transaction.updated","timestamp":1}'
    sig = hmac.new(b"test-only", raw, hashlib.sha256).hexdigest().upper()
    assert verify_signature(raw, "v1=other,v1=" + sig, "test-only")
    assert not verify_signature(raw + b" ", "v1=" + sig, "test-only")
    assert not verify_signature(raw, "v0=" + sig, "test-only")
    assert not verify_signature(raw, "v1=" + sig, "")


def test_bridge_published_signature_vector():
    raw = b'{"content":{"item_id":1234567890,"status":0,"user_uuid":"9a95b38f-f98b-417a-988b-9d0d584893e7"},"timestamp":1611681789,"type":"TEST_EVENT"}'
    assert verify_signature(raw, "v1=FAA8ECAC21DA6405D789C76EDB4003756398E7169DACC3FA70CF5919A81374A8", "644b2ac3-0797-4ec6-9537-cb5c0af9caf9")


@pytest.mark.parametrize("status,amount,currency,reference,ok", [("ACSC", "12.00", "EUR", "order-demo", True), ("PDNG", "12.00", "EUR", "order-demo", False), ("ACSC", "12.01", "EUR", "order-demo", False), ("ACSC", "12.00", "USD", "order-demo", False), ("ACSC", "12.00", "EUR", "another", False)])
def test_only_exact_settlement_unlocks(status, amount, currency, reference, ok):
    value = {"status": status, "client_reference": reference, "transactions": [{"status": status, "amount": amount, "currency": currency}]}
    assert settled_for_order(value, ORDER) is ok


def test_kiosk_link_stays_on_public_bridge_page_and_expires_in_ten_minutes(monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setenv("BRIDGE_FLOW", "payment_link")
    monkeypatch.setenv("BRIDGE_BENEFICIARY_MODE", "default")
    monkeypatch.setenv("BRIDGE_CALLBACK_URL", "http://127.0.0.1:5190")
    payload = payment_payload({**ORDER, "channel": "automate", "traveler": "adult"})
    assert "callback_url" not in payload
    assert payload["user"]["first_name"] == "Alex"
    assert payload["client_reference"] == ORDER["id"]
    seconds = (datetime.fromisoformat(payload["expired_date"].replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds()
    assert 590 < seconds <= 600
    assert payment_payload(ORDER)["callback_url"] == "http://127.0.0.1:5190"


def test_create_link_preserves_expiry_for_kiosk(monkeypatch):
    import httpx
    from maas import bridge
    monkeypatch.setattr(bridge, "headers", lambda: {})
    monkeypatch.setattr(bridge.httpx, "post", lambda *a, **kw: httpx.Response(200, request=httpx.Request("POST", bridge.LINKS), json={"id": "link-id", "url": "https://pay.bridgeapi.io/link/demo"}))
    value = bridge.create_payment({"provider_id": 574, "expired_date": "2026-10-25T12:00:00Z"})
    assert value["expires_at"] == "2026-10-25T12:00:00Z"
