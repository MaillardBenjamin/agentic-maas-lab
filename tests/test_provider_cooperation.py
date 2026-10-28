"""Business boundaries of distributed consultation and per-supplier settlement."""
import copy
from datetime import date

import jwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from maas import knowledge, providers
from maas.db import Base, Record
from maas.domain import CATALOG, allocate_refund, describe_quote, quote, settlement
from maas.organizations import organization, provider_scope, read_scope, sign_scope
from maas.partner_grants import read_grant
from maas.security import USERS, token


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "supplier-test-secret-01234567890123456789")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(providers, "Session", factory)
    seen = []
    def sources(question, graph):
        seen.append(graph)
        return [{"id": next(s["id"] for s in CATALOG["sources"] if s["provider"] == p), "graph": graph} for p in [next(o["id"] for o in CATALOG["organizations"] if o["graph"] == graph)]]
    monkeypatch.setattr(knowledge, "search_sources", sources)
    prepared = quote(USERS["lea"], ["transport", "parking", "bike"], "agency", "2026-10-28")
    with factory.begin() as db:
        for oid, traveler in [("mine", "lea"), ("other", "adult")]:
            db.add(Record(id=oid, kind="order", data={"id": oid, "traveler": traveler, "org": "alize", "quote": prepared, "state": "fulfilled", "payment_count": 1, "refund_cents": 0}))
        db.add(Record(id=providers.inventory_id("alize", "parking"), kind="partner_inventory", data={"available": ["space-1"]}))
    def get(db, oid, kind):
        rec = db.get(Record, oid)
        if not rec or rec.kind != kind:
            raise HTTPException(404)
        return rec
    def statement(oid, user):
        with factory() as db:
            return settlement(get(db, oid, "order").data, 0)
    app = FastAPI()
    providers.register(app, get, statement)
    with TestClient(app) as client:
        yield client, factory, seen


def headers(provider="parking", order_id=None, identity="lea", **kw):
    user = USERS[identity]
    return {"Authorization": "Bearer " + token(user), "X-MaaS-Provider-Read": provider_scope(user, provider, order_id, traveler=identity if identity in ("lea", "adult") else None, **kw)}


def test_price_and_availability_before_purchase_do_not_create_effects(setup):
    client, factory, seen = setup
    response = client.post("/api/provider-tools/parking/context", headers=headers(), json={"question": "Peux-tu me donner le tarif du parking ?"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["provider_org"] == "parking-relais"
    assert [p["id"] for p in data["products"]] == ["parking"]
    assert data["price_preview"]["total_cents"] == 500
    assert data["availability"]["available_count"] == 1 and not data["availability"]["reservation_guaranteed"]
    assert "order" not in data and seen == ["parking_demo"]
    with factory() as db:
        assert len(db.get(Record, providers.inventory_id("alize", "parking")).data["available"]) == 1
        assert db.get(Record, "mine").data["state"] == "fulfilled"


def test_supplier_and_identity_scopes_cannot_be_widened(setup):
    client, _, _ = setup
    path = "/api/provider-tools/bike/context"
    assert client.post(path, headers=headers("parking"), json={"question": "offre"}).status_code == 403
    assert client.post(path, headers={"Authorization": "Bearer " + token(USERS["lea"])}, json={"question": "offre"}).status_code == 403
    stolen = headers("bike", identity="adult")
    stolen["Authorization"] = "Bearer " + token(USERS["lea"])
    assert client.post(path, headers=stolen, json={"question": "offre"}).status_code == 403
    with pytest.raises(jwt.InvalidTokenError):
        read_grant(headers()["X-MaaS-Provider-Read"])
    with pytest.raises(ValueError):
        organization("parking", "other-tenant")


def test_supplier_order_is_projected_and_wrong_traveler_refused(setup):
    client, _, _ = setup
    r = client.post("/api/provider-tools/parking/context", headers=headers(order_id="mine"), json={"question": "expliquer mon relevé"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert [l["product"] for l in data["order"]["lines"]] == ["parking"]
    assert [l["provider"] for l in data["statement"]] == ["parking"]
    assert "birth_date" not in str(data) and "student_until" not in str(data)
    r = client.post("/api/provider-tools/parking/context", headers=headers(order_id="other"), json={"question": "dossier"})
    assert r.status_code == 403


def test_contract_rates_and_refunds_are_kept_per_supplier():
    prepared = quote(USERS["lea"], ["transport", "parking", "bike"], "agency", "2026-10-28")
    prepared["lines"][1]["distribution_contract"]["commission_bps"] = 1000
    order = {"quote": prepared, "payment_count": 1, "refund_allocations": {"parking": 200}}
    result = settlement(order, 200, 300)
    transport, parking, bike = result["per_provider"]
    assert transport["seller_commission_cents"] == 35
    assert parking["seller_commission_cents"] == 30 and parking["operator_cents"] == 270
    assert bike["commission_pending_cents"] == 15 and bike["operator_pending_cents"] == 285
    assert result["seller_commission_cents"] == 65
    assert sum(l["net_prepaid_cents"] for l in result["per_provider"]) == 1000
    assert result["operators_cents"] + result["seller_commission_cents"] == 1000
    # Published catalog changes cannot rewrite the accepted contract snapshot.
    before = copy.deepcopy(result)
    original = CATALOG["distribution_contracts"][0]["commission_bps"]
    try:
        CATALOG["distribution_contracts"][0]["commission_bps"] = 9000
        assert settlement(order, 200, 300) == before
    finally:
        CATALOG["distribution_contracts"][0]["commission_bps"] = original


def test_cent_allocation_is_conserved_and_line_refund_is_bounded():
    lines = [{"product": "transport", "amount_cents": 101}, {"product": "parking", "amount_cents": 100}]
    allocation = allocate_refund(lines, 99)
    assert sum(allocation.values()) == 99
    assert allocate_refund(lines, 100, product="parking") == {"parking": 100}
    with pytest.raises(ValueError):
        allocate_refund(lines, 101, product="parking")
    with pytest.raises(ValueError):
        allocate_refund(lines, 1, product="missing")


def test_commissions_are_rounded_by_line_before_totaling():
    prepared = quote(USERS["lea"], ["transport", "parking"], "agency", "2026-10-28")
    for line in prepared["lines"]:
        line["amount_cents"] = 101
        line["distribution_contract"]["commission_bps"] = 5000
    prepared["total_cents"] = 202
    result = settlement({"quote": prepared, "payment_count": 1}, 0)
    assert result["seller_commission_cents"] == 102
    assert result["operators_cents"] == 100


def test_unpublished_distribution_agreement_cannot_produce_a_quote():
    with pytest.raises(ValueError, match="Accord de distribution absent"):
        quote({**USERS["lea"], "org": "unrelated"}, ["parking"], "app", "2026-10-28")


def test_customer_proposal_uses_euros_and_separates_postpaid_without_model_calculation():
    prepared = quote(USERS["lea"], ["transport", "parking", "bike"], "app", "2026-10-29")
    text = describe_quote(prepared)
    assert "29/10/2026" in text and "7,00 €" in text and "5,00 €" in text and "12,00 €" in text
    assert "500 €" not in text and "BPS" not in text
    assert "après usage" in text and "0,20 €/minute commencée" in text
    assert "Aucune réservation ni commande" in text


def test_read_scope_is_bound_to_role_actor_tenant_and_audience(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "supplier-test-secret-01234567890123456789")
    value = sign_scope("maas-coordination", USERS["lea"], traveler="lea", seller="app")
    assert read_scope(value, "maas-coordination", USERS["lea"])["traveler"] == "lea"
    for user in [USERS["adult"], {**USERS["lea"], "org": "elsewhere"}, {**USERS["lea"], "role": "supervisor"}]:
        with pytest.raises(jwt.InvalidTokenError):
            read_scope(value, "maas-coordination", user)
