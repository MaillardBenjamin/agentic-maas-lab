"""The assistant's reviewable offer stays bound to the authenticated sales context."""
import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from maas import integrations
from maas.db import Base, Record
from maas.domain import quote
from maas.organizations import read_scope
from maas.security import USERS, token


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "chat-cooperation-test-secret-0123456789")
    monkeypatch.setattr(integrations, "chat_backend", lambda: "ollama_local")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(integrations, "Session", factory)
    prepared = {**quote(USERS["lea"], ["parking"], "agency", "2026-10-29"), "id": "proposed", "org": "alize", "traveler": "lea"}
    with factory.begin() as db:
        db.add(Record(id="proposed", kind="quote", data=prepared))
        db.add(Record(id="selected", kind="order", data={"id": "selected", "org": "alize", "traveler": "lea", "state": "fulfilled", "quote": prepared}))
    captured = []
    def remote(request):
        captured.append(request)
        return httpx.Response(200, json={"result": {"status": {"state": "completed"}, "artifacts": [{"parts": [{"kind": "text", "text": "Proposition libre incorrecte : 500 €"}]}]}}, headers={"X-MaaS-Proposal-ID": "proposed", "X-MaaS-MCP-Tools": "read_provider_context,prepare_quote", "X-MaaS-A2A-Agents": "mobility,parking"})
    original = httpx.AsyncClient
    monkeypatch.setattr(integrations.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(remote), **kw))
    def get(db, rid, kind=None):
        record = db.get(Record, rid)
        if not record or (kind and record.kind != kind):
            raise HTTPException(404)
        return record
    app = FastAPI()
    integrations.register(app, get, None, lambda *a: None)
    with TestClient(app) as client:
        yield client, factory, captured


def auth(identity):
    return {"Authorization": "Bearer " + token(USERS[identity])}


def test_advisor_proposal_uses_selected_customer_seller_and_deterministic_display(setup):
    client, factory, captured = setup
    response = client.post("/api/chat", headers=auth("clerk"), json={"message": "Prépare une offre parking pour le 2026-10-29", "traveler": "lea", "seller": "agency", "order_id": "selected"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["proposal"]["traveler"] == "lea" and data["proposal"]["seller"] == "agency"
    assert "5,00 €" in data["text"] and "500 €" not in data["text"]
    scope = read_scope(captured[0].headers["X-MaaS-Coordination"], "maas-coordination", USERS["clerk"])
    assert (scope["traveler"], scope["seller"], scope["order_id"], scope["providers"]) == ("lea", "agency", "selected", ["parking"])
    with factory() as db:
        assert db.get(Record, "selected").data["state"] == "fulfilled"


def test_traveler_cannot_prepare_for_another_customer_or_agency(setup):
    client, _, captured = setup
    for patch in [{"traveler": "adult"}, {"seller": "agency"}, {"order_id": "selected", "traveler": "adult"}]:
        response = client.post("/api/chat", headers=auth("lea"), json={"message": "Prépare un devis", **patch})
        assert response.status_code == 403
    assert not captured


def test_mismatched_returned_proposal_is_not_displayed(setup):
    client, factory, _ = setup
    with factory.begin() as db:
        row = db.get(Record, "proposed")
        row.data = {**row.data, "traveler": "adult"}
    response = client.post("/api/chat", headers=auth("clerk"), json={"message": "Prépare un devis parking", "traveler": "lea", "seller": "agency"})
    assert response.status_code == 502
