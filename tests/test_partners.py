from datetime import datetime, timedelta, timezone
import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from maas.db import Base, Record
from maas import partners
from maas.partner_grants import grant_for, read_grant
from maas.security import USERS, token


@pytest.fixture
def sessions(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(partners, "Session", factory)
    monkeypatch.setenv("JWT_SECRET", "unit-test-partner-signing-secret-0123456789")
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("AGENT_MODE", "ollama")
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
    partners.initialize_inventory()
    with factory.begin() as db:
        db.add(Record(id="order-test", kind="order", data={"id": "order-test", "org": "alize", "traveler": "lea", "state": "fulfilled", "quote": {"lines": [{"product": "bike"}, {"product": "parking"}]}}))
    return factory


def operation(sessions, action, partner="bike", key=None, seconds=None):
    body = partners.PartnerRequest(partner=partner, action=action, confirmed=True, idempotency_key=key or "unit-test-" + partner + "-" + action, duration_seconds=seconds)
    with sessions.begin() as db:
        value = partners.prepare_operation(db, "order-test", body, USERS["lea"], lambda *a: None)
        rec = db.get(Record, value["id"])
        rec.data = {**rec.data, "availability_checked": True}
        return rec.data


def apply(sessions, op):
    with sessions.begin() as db:
        return partners.apply_operation(db, read_grant(grant_for(op)), op["partner"], lambda *a: None)


def test_reserve_replay_and_return_emit_one_event(sessions):
    reserved = operation(sessions, "reserve")
    first = apply(sessions, reserved)
    assert apply(sessions, reserved) == first
    apply(sessions, operation(sessions, "start"))
    returned = operation(sessions, "finish", seconds=600)
    receipt = apply(sessions, returned)
    assert apply(sessions, returned) == receipt
    assert receipt["booking"]["state"] == "completed" and receipt["effect_count"] == 1
    assert apply(sessions, operation(sessions, "finish", key="another-finish-key", seconds=600))["effect_count"] == 0
    with sessions() as db:
        events = list(db.scalars(select(Record).where(Record.kind == "event")))
        assert len(events) == 1
        assert events[0].data["data"]["seconds"] == 600
        assert events[0].data["source"] == "urn:partner:bike"
        assert len(db.get(Record, "inventory-alize-bike").data["available"]) == 2
    with pytest.raises(HTTPException) as exc:
        apply(sessions, operation(sessions, "finish", key="contradictory-finish", seconds=601))
    assert exc.value.status_code == 409


def test_cancellation_restores_stock_and_new_reservation_identity(sessions):
    first = apply(sessions, operation(sessions, "reserve"))["booking"]
    apply(sessions, operation(sessions, "cancel"))
    second = apply(sessions, operation(sessions, "reserve", key="reserve-after-cancel"))["booking"]
    assert second["reservation_id"] != first["reservation_id"]
    with sessions() as db:
        assert len(db.get(Record, "inventory-alize-bike").data["available"]) == 1


def test_stock_empty_never_invents_a_resource(sessions):
    with sessions.begin() as db:
        row = db.get(Record, "inventory-alize-bike")
        row.data = {**row.data, "available": []}
    with pytest.raises(HTTPException) as exc:
        apply(sessions, operation(sessions, "reserve"))
    assert exc.value.status_code == 409
    with sessions() as db:
        assert not list(db.scalars(select(Record).where(Record.kind == "partner_booking")))


@pytest.mark.parametrize("action,state", [("start", "available"), ("finish", "reserved"), ("cancel", "active")])
def test_invalid_lifecycle_is_refused(action, state):
    with pytest.raises(HTTPException) as exc:
        partners.transition({"state": state}, ["bike-demo-1"], action, 600 if action == "finish" else None, "booking")
    assert exc.value.status_code == 409


def test_wrong_traveler_and_missing_product_refused(sessions):
    body = partners.PartnerRequest(partner="bike", action="reserve", confirmed=True, idempotency_key="wrong-principal")
    with sessions.begin() as db, pytest.raises(HTTPException) as exc:
        partners.prepare_operation(db, "order-test", body, USERS["adult"], lambda *a: None)
    assert exc.value.status_code == 403
    with sessions.begin() as db:
        row = db.get(Record, "order-test")
        row.data = {**row.data, "quote": {"lines": [{"product": "transport"}]}}
    with sessions.begin() as db, pytest.raises(HTTPException) as exc:
        partners.prepare_operation(db, "order-test", body, USERS["lea"], lambda *a: None)
    assert exc.value.status_code == 409


def test_idempotency_key_cannot_change_action(sessions):
    operation(sessions, "reserve", key="same-operation-key")
    with pytest.raises(HTTPException) as exc:
        operation(sessions, "start", key="same-operation-key")
    assert exc.value.status_code == 409


def test_grant_is_bound_to_actor_partner_action_and_audience(sessions):
    op = operation(sessions, "reserve")
    signed = grant_for(op)
    claims = read_grant(signed)
    for patch in ({"actor": "adult"}, {"partner": "parking"}, {"action": "finish"}, {"fixture": True}):
        with sessions.begin() as db, pytest.raises(HTTPException) as exc:
            partners.apply_operation(db, {**claims, **patch}, "bike", lambda *a: None)
        assert exc.value.status_code == 403
    with pytest.raises(jwt.InvalidTokenError):
        read_grant(token(USERS["lea"]))
    wrong_audience = jwt.encode({**claims, "aud": "maas-demo"}, "unit-test-partner-signing-secret-0123456789", algorithm="HS256")
    with pytest.raises(jwt.InvalidAudienceError):
        read_grant(wrong_audience)
    expired = jwt.encode({**claims, "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}, "unit-test-partner-signing-secret-0123456789", algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        read_grant(expired)


def test_availability_must_be_consulted_before_effect(sessions):
    op = operation(sessions, "reserve")
    with sessions.begin() as db:
        row = db.get(Record, op["id"])
        row.data = {**row.data, "availability_checked": False}
    with pytest.raises(HTTPException) as exc:
        apply(sessions, op)
    assert exc.value.status_code == 409


@pytest.mark.parametrize("change", [{"confirmed": False}, {"duration_seconds": 600}, {"partner": "car"}, {"action": "pay"}])
def test_unconfirmed_or_unscoped_requests_rejected(change):
    with pytest.raises(ValidationError):
        partners.PartnerRequest(**{"partner": "bike", "action": "reserve", "confirmed": True, "idempotency_key": "test-invalid-request", **change})


def test_agno_history_only_response_is_visible_without_echoing_user_message():
    task = {"history": [{"role": "user", "parts": [{"kind": "text", "text": "Réserve un vélo"}]}, {"role": "agent", "parts": [{"kind": "text", "text": "Réservation confirmée par le service simulé."}]}]}
    assert partners.task_explanation(task) == "Réservation confirmée par le service simulé."


def test_a2a_artifact_takes_precedence_over_history():
    task = {"artifacts": [{"parts": [{"kind": "text", "text": "Résultat final"}]}], "history": [{"role": "agent", "parts": [{"kind": "text", "text": "Message intermédiaire"}]}]}
    assert partners.task_explanation(task) == "Résultat final"
