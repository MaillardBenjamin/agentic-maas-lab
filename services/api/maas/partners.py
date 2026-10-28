"""Stateful fictive operators. LLM text never authorizes or confirms an effect."""
import os
import uuid
from datetime import datetime, timezone
from typing import Literal

import httpx
import jwt
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from maas import agent_activity
from maas.ai import chat_backend
from maas.budget import reserve
from maas.db import Record, Session
from maas.domain import digest
from maas.events import store_event
from maas.partner_grants import grant_for, read_grant
from maas.organizations import organization
from maas.providers import inventory_id
from maas.security import access, principal, service, token


def now():
    return datetime.now(timezone.utc).isoformat()


def task_explanation(task):
    texts = [p["text"] for a in task.get("artifacts", []) for p in a.get("parts", []) if p.get("kind") == "text"]
    if not texts:
        texts = [p["text"] for m in task.get("history", []) if m.get("role") == "agent" for p in m.get("parts", []) if p.get("kind") == "text"]
    return "\n".join(texts)[:2000]


def initialize_inventory():
    with Session.begin() as db:
        for partner in ("bike", "parking"):
            # Copy a legacy stock once; never reset reservations on an upgrade.
            legacy = db.get(Record, "inventory-alize-" + partner)
            values = {"id": inventory_id("alize", partner), "kind": "partner_inventory", "data": {"partner": partner, "org": "alize", "provider_org": organization(partner)["org"], "available": list(legacy.data["available"]) if legacy else [partner + "-demo-1", partner + "-demo-2"]}}
            if db.bind.dialect.name == "postgresql":
                db.execute(insert(Record).values(**values).on_conflict_do_nothing(index_elements=["id"]))
            elif not db.get(Record, values["id"]):
                db.add(Record(**values))


class PartnerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    partner: Literal["bike", "parking"]
    action: Literal["reserve", "start", "finish", "cancel"]
    confirmed: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    duration_seconds: int | None = Field(default=None, ge=0, le=86400, strict=True)

    @model_validator(mode="after")
    def duration_scope(self):
        timed = self.partner == "bike" and self.action == "finish"
        if timed != (self.duration_seconds is not None):
            raise ValueError("Durée requise uniquement pour la restitution du vélo")
        return self


def record(db, rid, kind, lock=False):
    query = select(Record).where(Record.id == rid, Record.kind == kind)
    value = db.scalar(query.with_for_update() if lock else query)
    if not value:
        raise HTTPException(404, "Référence partenaire inconnue")
    return value


def prepare_operation(db, oid, body, user, log, test_only=False):
    order = record(db, oid, "order", lock=True).data
    access(user, order)
    if user["role"] not in ("traveler", "demo", "clerk", "supervisor"):
        raise HTTPException(403, "Profil non autorisé")
    if order["state"] != "fulfilled" or body.partner not in [p["product"] for p in order["quote"]["lines"]]:
        raise HTTPException(409, "Droit partenaire absent ou non délivré")
    oid_key = "partner-op-" + digest({"org": user["org"], "actor": user["id"], "key": body.idempotency_key})
    fingerprint = digest({"order_id": oid, **body.model_dump(), "test_only": test_only})
    existing = db.get(Record, oid_key)
    if existing:
        if existing.data["request_digest"] != fingerprint:
            raise HTTPException(409, "Clé partenaire déjà liée à une autre demande")
        return existing.data
    value = {"id": oid_key, "order_id": oid, "org": user["org"], "provider_org": organization(body.partner, user["org"])["org"], "partner": body.partner, "action": body.action, "duration_seconds": body.duration_seconds, "actor": {k: user[k] for k in ("id", "role", "org")}, "request_digest": fingerprint, "test_only": test_only, "requested_backend": "fixture-no-llm" if test_only else chat_backend(), "status": "queued", "created_at": now(), "availability_checked": False, "effect_count": 0}
    db.add(Record(id=oid_key, kind="partner_operation", data=value))
    log(db, "partner.operation.confirmed", {"order_id": oid, "org": user["org"], "operation_id": oid_key, "partner": body.partner, "action": body.action, "test_only": test_only})
    return value


def transition(booking, available, action, duration, booking_id):
    """Deterministic lifecycle. Mutates copies, and never invents a resource."""
    state = booking.get("state", "available")
    value, stock = dict(booking), list(available)
    if action == "reserve":
        if state in ("reserved", "active"):
            return value, stock, False
        if state == "completed":
            raise HTTPException(409, "Droit déjà consommé")
        if not stock:
            raise HTTPException(409, "Aucune ressource disponible chez le partenaire simulé")
        generation = value.get("generation", 0) + 1
        value.update(state="reserved", asset_id=stock.pop(0), generation=generation, reservation_id=booking_id + "-" + str(generation), reserved_at=now())
    elif action == "start":
        if state == "active":
            return value, stock, False
        if state != "reserved":
            raise HTTPException(409, "Réservation requise avant le début d’usage")
        value.update(state="active", started_at=now())
    elif action == "cancel":
        if state == "cancelled":
            return value, stock, False
        if state != "reserved":
            raise HTTPException(409, "Seule une réservation non utilisée peut être annulée")
        stock.append(value["asset_id"])
        value.update(state="cancelled", ended_at=now())
    elif action == "finish":
        if state == "completed":
            if value.get("duration_seconds") != duration:
                raise HTTPException(409, "Durée contradictoire avec la restitution enregistrée")
            return value, stock, False
        if state != "active":
            raise HTTPException(409, "Usage actif requis avant restitution ou sortie")
        stock.append(value["asset_id"])
        value.update(state="completed", duration_seconds=duration, ended_at=now())
    else:
        raise HTTPException(422, "Action inconnue")
    return value, sorted(stock), True


def tool_principal(authorization: str = Header(default="")):
    try:
        scheme, value = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise ValueError()
        return read_grant(value)
    except (ValueError, jwt.PyJWTError):
        raise HTTPException(401, "Autorisation partenaire signée requise")


def scoped_operation(db, claims, partner=None, lock=False):
    rec = record(db, claims["sub"], "partner_operation", lock)
    op = rec.data
    if (op["actor"]["id"], op["org"], op["partner"], op["action"], op["test_only"], op["requested_backend"]) != (claims["actor"], claims["org"], claims["partner"], claims["action"], claims["fixture"], claims["backend"]) or (partner and partner != op["partner"]):
        raise HTTPException(403, "Outil hors de la portée confirmée")
    order = record(db, op["order_id"], "order").data
    access(op["actor"], order)
    return rec, order


def apply_operation(db, claims, partner, log):
    rec, order = scoped_operation(db, claims, partner, lock=True)
    op = rec.data
    if op.get("result"):
        return op["result"]
    if op["status"] == "failed":
        raise HTTPException(409, op["error"])
    if not op["availability_checked"]:
        raise HTTPException(409, "Consulter d’abord la disponibilité via MCP")
    # Common lock order for both operators; serializes stock changes across orders.
    inventory = record(db, inventory_id(op["org"], partner), "partner_inventory", lock=True)
    bid = "partner-booking-" + digest({"org": op["org"], "order_id": order["id"], "partner": partner})
    booking = db.get(Record, bid)
    before = booking.data if booking else {"id": bid, "order_id": order["id"], "org": op["org"], "provider_org": organization(partner, op["org"])["org"], "partner": partner}
    value, stock, changed = transition(before, inventory.data["available"], op["action"], op["duration_seconds"], bid)
    if order["state"] != "fulfilled" or partner not in [p["product"] for p in order["quote"]["lines"]]:
        raise HTTPException(409, "Droit partenaire non délivré")
    event_id = value.get("event_id")
    if op["action"] == "finish" and changed:
        event = {"specversion": "1.0", "id": op["id"], "source": "urn:partner:" + partner, "type": "maas." + partner + ".ended.v1", "time": value["ended_at"], "data": {"order_id": order["id"], "passage_id": value["reservation_id"]}}
        if partner == "bike":
            event["data"]["seconds"] = op["duration_seconds"]
        event_id = store_event(db, event, order, op["org"], log)["id"]
        value["event_id"] = event_id
    inventory.data = {**inventory.data, "available": stock}
    if booking:
        booking.data = value
    else:
        db.add(Record(id=bid, kind="partner_booking", data=value))
    result = {"operation_id": op["id"], "partner": partner, "action": op["action"], "booking": value, "event_id": event_id, "effect_count": int(changed), "simulation": True}
    rec.data = {**op, "status": "executed", "result": result, "effect_count": int(changed), "executed_at": now()}
    log(db, "partner.effect.executed", {"order_id": order["id"], "org": op["org"], "operation_id": op["id"], "partner": partner, "action": op["action"], "changed": changed, "event_id": event_id})
    return result


async def dispatch_operation(opid, log, fixture=False):
    with Session.begin() as db:
        rec = record(db, opid, "partner_operation", lock=True)
        if rec.data["test_only"] != fixture:
            raise HTTPException(403, "Le double de modèle est réservé aux opérations de test")
        if rec.data["status"] in ("completed", "failed"):
            return rec.data
        op = dict(rec.data)
        rec.data = {**op, "status": "running", "attempts": op.get("attempts", 0) + 1}
    backend = "fixture-no-llm" if fixture else chat_backend()
    if not backend:
        raise HTTPException(503, "Fournisseur IA désactivé ; opération conservée pour reprise")
    if op["requested_backend"] != backend:
        raise HTTPException(503, "Fournisseur modifié depuis la confirmation ; aucun basculement automatique")
    if backend == "openai_via_agno":
        reserve(100)
    activity_id = agent_activity.start(op["actor"], "Coopération vélo" if op["partner"] == "bike" else "Coopération parking", backend)
    with agent_activity.exchange(activity_id, op["actor"], "A2A", "interface", "mobility"):
        request_id = str(uuid.uuid4())
        message = f"Opération confirmée {opid}. Partenaire {op['partner']}, action {op['action']}. Délègue au partenaire correspondant et rapporte son résultat sans inventer de succès."
        payload = {"jsonrpc": "2.0", "id": request_id, "method": "message/send", "params": {"message": {"messageId": request_id, "role": "user", "parts": [{"kind": "text", "text": message}]}}}
        target = os.environ.get("PARTNER_FIXTURE_A2A_URL", "http://agent-fixture:8002") if fixture else "http://agents:8002"
        async with httpx.AsyncClient(timeout=360) as client:
            response = await client.post(target + "/a2a/agents/mobility_operations/v1/message:send", json=payload, headers={"Authorization": "Bearer " + token(op["actor"]), "X-MaaS-Partner-Grant": grant_for(op), "X-MaaS-Activity-ID": activity_id})
            response.raise_for_status()
            task = response.json().get("result", {})
        tools = sorted(set(filter(None, response.headers.get("X-MaaS-MCP-Tools", "").split(","))))
        delegates = list(filter(None, response.headers.get("X-MaaS-A2A-Agents", "").split(",")))
        required = {op["partner"] + "_availability", op["partner"] + "_apply"}
        if response.headers.get("X-MaaS-Runtime-Mode") != ("fixture" if fixture else "ollama" if backend == "ollama_local" else "openai"):
            raise HTTPException(503, "Fournisseur du runtime différent de celui confirmé")
        if task.get("status", {}).get("state") != "completed" or op["partner"] not in delegates or not required.issubset(tools):
            raise HTTPException(503, "Parcours A2A/MCP incomplet ; aucun succès déduit du texte IA")
        with Session.begin() as db:
            rec = record(db, opid, "partner_operation", lock=True)
            if rec.data["status"] == "failed":
                return rec.data
            if not rec.data.get("result"):
                raise HTTPException(503, "Agent terminé sans effet métier vérifié")
            value = {**rec.data, "status": "completed", "mode": backend, "model": response.headers.get("X-MaaS-Model"), "provider": response.headers.get("X-MaaS-Provider"), "evidence": {"a2a_agents": ["mobility", *delegates], "mcp_tools": tools, "partner_runtime": "separate", "business_result_verified": True}, "explanation": task_explanation(task), "completed_at": now()}
            rec.data = value
            log(db, "partner.a2a.completed", {"order_id": op["order_id"], "org": op["org"], "operation_id": opid, "partner": op["partner"], "mode": backend, "mcp_tools": tools})
        return value


def register(app, temporal, log):
    async def enqueue(op):
        try:
            client = await temporal()
            await client.start_workflow("PartnerInteraction", {"operation_id": op["id"], "fixture": op["test_only"]}, id=op.get("workflow_id", op["id"]), task_queue="maas-ticketing", id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
        except WorkflowAlreadyStartedError:
            pass
        except Exception:
            raise HTTPException(503, {"message": "Opération conservée ; reprendre son suivi Temporal", "operation_id": op["id"]})

    @app.get("/api/orders/{oid}/partners")
    def partner_state(oid: str, user=Depends(principal)):
        with Session() as db:
            access(user, record(db, oid, "order").data)
            bookings = [r.data for r in db.scalars(select(Record).where(Record.kind == "partner_booking")) if r.data["order_id"] == oid]
            operations = [r.data for r in db.scalars(select(Record).where(Record.kind == "partner_operation").order_by(Record.created_at.desc())) if r.data["order_id"] == oid]
            availability = {p: len(record(db, inventory_id(user["org"], p), "partner_inventory").data["available"]) for p in ("bike", "parking")}
            return {"bookings": bookings, "operations": operations, "availability": availability, "simulation": True}

    @app.post("/api/orders/{oid}/partner-operations")
    async def begin(oid: str, body: PartnerRequest, user=Depends(principal)):
        try:
            backend = chat_backend()
        except ValueError as exc:
            raise HTTPException(503, str(exc))
        try:
            with Session.begin() as db:
                op = prepare_operation(db, oid, body, user, log)
                if not backend and op["status"] not in ("completed", "failed"):
                    raise HTTPException(503, "Activer un fournisseur IA pour la coopération A2A")
        except IntegrityError:
            with Session.begin() as db:
                op = prepare_operation(db, oid, body, user, log)
        if op["status"] not in ("completed", "failed"):
            await enqueue(op)
        return op

    @app.post("/api/partner-operations/{opid}/resume")
    async def resume(opid: str, confirmation: dict, user=Depends(principal)):
        if confirmation != {"confirmed": True}:
            raise HTTPException(422, "Confirmation explicite de reprise requise")
        with Session.begin() as db:
            rec = record(db, opid, "partner_operation", lock=True)
            access(user, record(db, rec.data["order_id"], "order").data)
            if rec.data["status"] == "completed":
                return rec.data
            if not rec.data["test_only"] and chat_backend() != rec.data["requested_backend"]:
                raise HTTPException(503, "Réactiver le fournisseur choisi lors de la confirmation")
            if rec.data["status"] == "failed":
                attempt = rec.data.get("resume_count", 0) + 1
                previous = rec.data.get("previous_errors", []) + [rec.data.get("error", "Échec du parcours")]
                rec.data = {**rec.data, "status": "queued", "resume_count": attempt, "workflow_id": opid + "-retry-" + str(attempt), "previous_errors": previous[-5:], "error": None}
                log(db, "partner.operation.resumed", {"org": rec.data["org"], "order_id": rec.data["order_id"], "operation_id": opid})
            op = rec.data
        await enqueue(op)
        return op

    @app.get("/api/partner-tools/{partner}/availability")
    def availability(partner: Literal["bike", "parking"], claims=Depends(tool_principal)):
        with Session.begin() as db:
            rec, order = scoped_operation(db, claims, partner, lock=True)
            stock = record(db, inventory_id(order["org"], partner), "partner_inventory").data
            rec.data = {**rec.data, "availability_checked": True}
            return {"partner": partner, "available_count": len(stock["available"]), "simulation": True, "confirmed_action": rec.data["action"], "operation_id": rec.id}

    @app.post("/api/partner-tools/{partner}/apply")
    def apply(partner: Literal["bike", "parking"], claims=Depends(tool_principal)):
        try:
            with Session.begin() as db:
                return apply_operation(db, claims, partner, log)
        except HTTPException as exc:
            if exc.status_code == 409:
                with Session.begin() as db:
                    rec, _ = scoped_operation(db, claims, partner, lock=True)
                    if not rec.data.get("result"):
                        rec.data = {**rec.data, "status": "failed", "error": str(exc.detail)}
            raise

    @app.post("/internal/partner-operations/{opid}/dispatch", dependencies=[Depends(service)])
    async def dispatch(opid: str, payload: dict):
        try:
            return await dispatch_operation(opid, log, fixture=payload.get("fixture") is True)
        except (httpx.HTTPError, ValueError, KeyError):
            raise HTTPException(503, "Agents partenaires indisponibles ; reprise idempotente requise")

    @app.post("/internal/partner-operations/{opid}/failed", dependencies=[Depends(service)])
    def failed(opid: str):
        with Session.begin() as db:
            rec = record(db, opid, "partner_operation", lock=True)
            if rec.data["status"] != "completed":
                rec.data = {**rec.data, "status": "failed", "error": "Parcours agent interrompu ; consulter le résultat métier enregistré avant un nouvel essai."}
            return rec.data
