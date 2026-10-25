import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy

from maas.db import Record, Session, initialize
from maas.domain import CATALOG, bike_price, digest, quote, settlement
from maas.security import USERS, access, authorize, principal, service, token


def utc():
    return datetime.now(timezone.utc).isoformat()


def get(db, rid, kind=None, lock=False):
    stmt = select(Record).where(Record.id == rid)
    if lock:
        stmt = stmt.with_for_update()
    rec = db.scalar(stmt)
    if not rec or (kind and rec.kind != kind):
        raise HTTPException(404, "Référence inconnue")
    return rec


def log(db, action, payload):
    rid = str(uuid.uuid4())
    db.add(Record(id=rid, kind="audit", data={"id": rid, "at": utc(), "action": action, "org": "alize", **payload}))


@asynccontextmanager
async def lifespan(app):
    initialize()
    from maas.partners import initialize_inventory
    initialize_inventory()
    from maas.observability import configure
    configure("maas-api")
    yield


app = FastAPI(title="MaaS agentique · démonstrateur", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5190", "http://127.0.0.1:5190"], allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])


@app.middleware("http")
async def trace_request(request, call_next):
    from opentelemetry import trace, propagate
    # No request body, query, headers or raw path exported (paths can contain identifiers).
    with trace.get_tracer("maas").start_as_current_span("http.request", context=propagate.extract(request.headers)) as span:
        span.set_attribute("http.request.method", request.method)
        response = await call_next(request)
        span.set_attribute("http.response.status_code", response.status_code)
        route = request.scope.get("route")
        if route:
            span.set_attribute("http.route", route.path)
        return response


class QuoteRequest(BaseModel):
    traveler: str = "lea"
    products: list[str] = ["transport", "parking", "bike"]
    seller: str = "agency"
    travel_date: str = "2026-10-24"


class Purchase(BaseModel):
    quote_id: str
    idempotency_key: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    channel: str = Field(default="web", pattern=r"^(web|automate|agency)$")
    pause_before_issue: bool = False
    payment_mode: str = Field(default="local_simulator", pattern=r"^(local_simulator|bridge_sandbox)$")


class Refund(BaseModel):
    amount_cents: int = Field(gt=0, le=100000)
    reason: str = Field(min_length=5, max_length=300)
    idempotency_key: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class Event(BaseModel):
    specversion: str = "1.0"
    id: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=120)
    type: str
    time: datetime
    data: dict


@app.get("/health")
def health():
    with Session() as db:
        db.execute(select(Record).limit(1))
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/demo/users")
def users():
    return list(USERS.values())


@app.post("/api/demo/login/{uid}")
def login(uid: str):
    # Explicitly local demo identity selector, NOT an OIDC provider or national identity.
    if uid not in USERS:
        raise HTTPException(404, "Profil inconnu")
    return {"access_token": token(USERS[uid]), "user": USERS[uid], "mode": "simulated_identity"}


@app.get("/api/catalog")
def catalog(user=Depends(principal)):
    return CATALOG


@app.post("/api/quotes")
def create_quote(body: QuoteRequest, user=Depends(principal)):
    if body.traveler not in USERS or USERS[body.traveler]["role"] != "traveler":
        raise HTTPException(422, "Voyageur inconnu")
    if user["role"] == "traveler" and user["id"] != body.traveler:
        raise HTTPException(403, "Profil hors périmètre")
    try:
        result = quote(USERS[body.traveler], body.products, body.seller, body.travel_date)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    result.update(id=str(uuid.uuid4()), traveler=body.traveler, org=user["org"], expires_at=(datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat())
    with Session.begin() as db:
        db.add(Record(id=result["id"], kind="quote", data=result))
        log(db, "quote.created", {"quote_id": result["id"], "principal": user["id"], "total_cents": result["total_cents"]})
    return result


async def temporal():
    from temporalio.contrib.opentelemetry import TracingInterceptor
    return await Client.connect(os.environ.get("TEMPORAL_ADDRESS", "temporal:7233"), interceptors=[TracingInterceptor()])


@app.post("/api/orders")
async def purchase(body: Purchase, user=Depends(principal)):
    oid = "order-" + digest({"org": user["org"], "user": user["id"], "key": body.idempotency_key})[:32]
    fingerprint = digest(body.model_dump())
    try:
        with Session.begin() as db:
            existing = db.get(Record, oid)
            if existing:
                access(user, existing.data)
                if existing.data["request_digest"] != fingerprint:
                    raise HTTPException(409, "Clé déjà utilisée pour une autre demande")
                result = existing.data
            else:
                q = get(db, body.quote_id, "quote").data
                access(user, q)
                if datetime.fromisoformat(q["expires_at"]) <= datetime.now(timezone.utc):
                    raise HTTPException(409, "Devis expiré : refaire une proposition")
                if body.payment_mode == "bridge_sandbox":
                    from maas.bridge import configured, payment_payload
                    if not configured():
                        raise HTTPException(503, "Bridge sandbox désactivé ou non configuré")
                    try:
                        payment_payload({"id": oid, "quote": q})
                    except ValueError as exc:
                        raise HTTPException(503, str(exc))
                result = {"id": oid, "org": q["org"], "traveler": q["traveler"], "quote": q, "channel": body.channel, "request_digest": fingerprint, "state": "payment_pending", "payment_mode": body.payment_mode, "payment_count": 0, "refund_cents": 0, "created_at": utc(), "pause_before_issue": body.pause_before_issue}
                db.add(Record(id=oid, kind="order", data=result))
                log(db, "order.confirmed", {"order_id": oid, "principal": user["id"], "channel": body.channel})
    except IntegrityError:
        # Concurrent identical confirmation: re-read instead of repeating an effect.
        with Session() as db:
            result = get(db, oid, "order").data
            if result["request_digest"] != fingerprint:
                raise HTTPException(409, "Clé déjà utilisée")
    try:
        client = await temporal()
        from temporalio.service import RPCError
        from temporalio.exceptions import WorkflowAlreadyStartedError
        try:
            await client.start_workflow("PurchaseAndIssue", {"order_id": oid, "pause": body.pause_before_issue}, id=oid, task_queue="maas-ticketing", id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
        except WorkflowAlreadyStartedError:
            pass
    except Exception:
        # Persisted order can be re-submitted with the same key after infrastructure recovery.
        raise HTTPException(503, {"message": "Commande persistée ; démarrage Temporal à reprendre avec la même clé", "order_id": oid})
    return result


@app.get("/api/orders")
def orders(user=Depends(principal)):
    with Session() as db:
        values = [r.data for r in db.scalars(select(Record).where(Record.kind == "order").order_by(Record.created_at.desc()))]
    return [v for v in values if v["org"] == user["org"] and (user["role"] != "traveler" or v["traveler"] == user["id"])]


@app.get("/api/orders/{oid}")
def order(oid: str, user=Depends(principal)):
    with Session() as db:
        result = get(db, oid, "order").data
        access(user, result)
        events = [r.data for r in db.scalars(select(Record).where(Record.kind == "event")) if r.data["data"].get("order_id") == oid]
        return {**result, "events": events}


@app.post("/api/demo/orders/{oid}/pay")
async def pay(oid: str, user=Depends(principal)):
    if user["role"] not in ("traveler", "demo", "clerk", "supervisor"):
        raise HTTPException(403)
    with Session.begin() as db:
        rec = get(db, oid, "order", lock=True)
        access(user, rec.data)
        data = dict(rec.data)
        if data["payment_mode"] != "local_simulator":
            raise HTTPException(409, "Paiement externe non simulable par cette commande")
        if not data["payment_count"]:
            data.update(payment_count=1, state="paid", paid_at=utc())
            rec.data = data
            log(db, "payment.confirmed.simulated", {"order_id": oid, "amount_cents": data["quote"]["total_cents"]})
    try:
        client = await temporal()
        await client.get_workflow_handle(oid).signal("payment_confirmed")
    except Exception:
        raise HTTPException(503, "Paiement simulé persisté ; répéter cette notification pour reprendre")
    return {"status": "confirmed", "mode": "simulated"}


@app.post("/api/demo/orders/{oid}/continue")
async def resume(oid: str, user=Depends(principal)):
    with Session() as db:
        access(user, get(db, oid, "order").data)
    client = await temporal()
    await client.get_workflow_handle(oid).signal("continue_issuance")
    return {"status": "signaled"}


@app.post("/internal/orders/{oid}/state", dependencies=[Depends(service)])
def internal_state(oid: str, payload: dict):
    if payload.get("state") not in ("awaiting_resume", "issuance_pending", "fulfilled", "reconciliation_required"):
        raise HTTPException(422)
    with Session.begin() as db:
        rec = get(db, oid, "order", lock=True)
        data = dict(rec.data)
        if data["state"] == "fulfilled":
            return data
        if not data["payment_count"]:
            raise HTTPException(409, "Émission interdite sans paiement confirmé")
        data.update(payload)
        rec.data = data
        log(db, "order." + data["state"], {"order_id": oid, "mode": "simulated_card"})
    return data


@app.post("/api/events")
def ingest(body: Event, user=Depends(principal)):
    from maas.events import store_event
    if user["role"] != "demo":
        raise HTTPException(403, "Console de simulation requise")
    # A concurrent delivery can win the unique event key; retry the ledger check once.
    for attempt in range(2):
        try:
            with Session.begin() as db:
                order = get(db, body.data.get("order_id"), "order").data
                access(user, order)
                return store_event(db, body.model_dump(mode="json"), order, user["org"], log)
        except IntegrityError:
            if attempt:
                raise


@app.get("/api/orders/{oid}/statement")
def statement(oid: str, user=Depends(principal)):
    with Session() as db:
        value = get(db, oid, "order").data
        access(user, value)
        events = [r.data for r in db.scalars(select(Record).where(Record.kind == "event")) if r.data["data"].get("order_id") == oid]
        # A rental is billed once per rental identifier, not per received message.
        rentals = {}
        bike_terms = next((line.get("terms") for line in value["quote"]["lines"] if line["product"] == "bike"), None)
        for e in events:
            if e["type"] == "maas.bike.ended.v1":
                rentals[e["data"]["passage_id"]] = bike_price(e["data"]["seconds"], bike_terms)
        result = settlement(value, value["refund_cents"], sum(rentals.values()))
        parking = any(e["type"] == "maas.parking.ended.v1" for e in events)
        validated = any(e["type"] == "maas.validation.accepted.v1" for e in events)
        parking_line = next((l for l in value["quote"]["lines"] if l["product"] == "parking"), None)
        reduction = max(0, parking_line["amount_cents"] - parking_line.get("terms", {}).get("validated_price_cents", 300)) if parking_line else 0
        result.update(order_id=oid, parking_adjustment_available_cents=reduction if parking and validated else 0, events_count=len(events))
        return result


@app.post("/api/orders/{oid}/refunds")
def refund(oid: str, body: Refund, user=Depends(principal)):
    rid = "refund-" + digest({"order": oid, "key": body.idempotency_key})
    fingerprint = digest(body.model_dump())
    try:
        with Session.begin() as db:
            rec = get(db, oid, "order", lock=True)
            authorize(user, "refund", rec.data, body.amount_cents)
            old = db.get(Record, rid)
            if old:
                if old.data["request_digest"] != fingerprint:
                    raise HTTPException(409, "Clé liée à une autre régularisation")
                return old.data
            if not rec.data["payment_count"] or body.amount_cents > rec.data["quote"]["total_cents"] - rec.data["refund_cents"]:
                raise HTTPException(409, "Montant restant insuffisant")
            value = {**rec.data, "refund_cents": rec.data["refund_cents"] + body.amount_cents}
            rec.data = value
            result = {"id": rid, "order_id": oid, "amount_cents": body.amount_cents, "principal": user["id"], "reason": body.reason, "request_digest": fingerprint, "mode": "simulated_refund", "status": "recorded"}
            db.add(Record(id=rid, kind="refund", data=result))
            log(db, "refund.recorded.simulated", result)
    except IntegrityError:
        raise HTTPException(409, "Opération concurrente : consulter la régularisation existante")
    return result


@app.get("/api/audit")
def audit(user=Depends(principal)):
    if user["role"] not in ("demo", "clerk", "supervisor"):
        raise HTTPException(403)
    with Session() as db:
        return [r.data for r in db.scalars(select(Record).where(Record.kind == "audit").order_by(Record.created_at.desc()).limit(100)) if r.data.get("org", "alize") == user["org"]]


@app.get("/api/integrations")
def integrations(user=Depends(principal)):
    from pathlib import Path
    from maas.bridge import configured
    ai = os.environ.get("AI_ENABLED") == "true" and os.environ.get("AGENT_MODE") == "openai" and bool(os.environ.get("OPENAI_API_KEY"))
    from maas.ai import chat_backend
    try:
        local = chat_backend() == "ollama_local"
    except ValueError:
        local = False
    return [{"name": n, "mode": m, "detail": d} for n, m, d in [
        ("Temporal", "real", "Workflow et Worker Docker persistants"),
        ("PostgreSQL", "real", "Commandes, paiements de test, événements et audit"),
        ("OPA", "real", "Décisions Rego côté service SAV"),
        ("Carte et paiement", "simulated", "État indépendant du Worker ; aucun argent réel"),
        ("FalkorDB", "real", "Grilles par acteur, sources, index textuel et vecteurs lexicaux locaux"),
        ("Agno / A2A / MCP", "real", "5 agents MaaS, 2 agents partenaires sur un runtime séparé, 8 outils MCP ; fournisseur : " + os.environ.get("AGENT_MODE", "disabled")),
        ("Partenaires vélo / parking", "simulated", "Agents A2A et MCP réels ; réservation et usage sur services fictifs avec état, confirmation limitée et reprise Temporal"),
        ("OpenAI", "configured" if ai else "unconfigured", "Mode cloud actif" if ai else "Clé présente mais fournisseur désactivé" if os.environ.get("OPENAI_API_KEY") else "Clé absente ; fournisseur désactivé"),
        ("Ollama", "configured" if local else "unconfigured", "Inférence locale : " + os.environ.get("OLLAMA_MODEL", "qwen3:14b") if local else "Option locale disponible via AGENT_MODE=ollama"),
        ("Bridge", "configured" if configured() else "unconfigured", "Pay by Link · Demo Bank sandbox ; confirmation ACSC relue côté serveur"),
        ("Anvil", "real" if Path("/proofs/deployment.json").exists() else "pending", "Contrat local, manifeste signé Ed25519, ancrage via Temporal"),
        ("Keyple", "real", "SDK Java réel : sélection, écriture et relecture sur carte stub ; sans SAM réel"),
        ("Harness²", "lab", "Code Google figé ; deux rapprochements fictifs en laboratoire isolé, éditeurs déterministes sans LLM"),
    ]]


@app.post("/api/knowledge/search")
def search(payload: dict, user=Depends(principal)):
    query = str(payload.get("query", ""))[:300]
    if not query.strip():
        raise HTTPException(422, "Question requise")
    try:
        from maas.knowledge import search_sources
        return {"mode": "graph_hybrid_local", "sources": search_sources(query), "note": "Index textuel + vecteurs lexicaux locaux + traversée du graphe. Aucun embedding sémantique OpenAI ni génération dans cette recherche."}
    except Exception:
        raise HTTPException(503, "Graphe indisponible ; aucune réponse de remplacement présentée comme issue du graphe")


@app.post("/api/proofs/{oid}")
async def create_proof(oid: str, user=Depends(principal)):
    if user["role"] != "demo":
        raise HTTPException(403)
    from maas.proofs import sign_manifest
    with Session.begin() as db:
        access(user, get(db, oid, "order").data)
        records = list(db.scalars(select(Record).where(Record.kind == "event").order_by(Record.id)))
        events = [{"type": r.data["type"], "time": r.data["time"], "business_digest": r.data["business_digest"]} for r in records if r.data["data"].get("order_id") == oid]
        if not events:
            raise HTTPException(409, "Aucun événement accepté pour ce lot")
        manifest = {"schema_version": 1, "events": events}
        batch_digest = digest(manifest)
        bid = "batch-" + batch_digest
        if not db.get(Record, bid):
            db.add(Record(id=bid, kind="proof", data={"id": bid, "manifest": manifest, "digest": batch_digest, **sign_manifest(manifest), "status": "pending"}))
    from temporalio.exceptions import WorkflowAlreadyStartedError
    client = await temporal()
    try:
        await client.start_workflow("ProofAnchoring", bid, id=bid, task_queue="maas-ticketing", id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
    except WorkflowAlreadyStartedError:
        pass
    return {"id": bid, "digest": batch_digest, "status": "pending"}


@app.get("/api/proofs")
def proofs(user=Depends(principal)):
    if user["role"] != "demo":
        raise HTTPException(403)
    with Session() as db:
        from maas.proofs import with_anchor_time
        return [with_anchor_time(r.data) for r in db.scalars(select(Record).where(Record.kind == "proof"))]


@app.post("/internal/proofs/{bid}/anchor", dependencies=[Depends(service)])
def anchor(bid: str):
    from maas.proofs import anchor_batch
    with Session.begin() as db:
        rec = get(db, bid, "proof", lock=True)
        if rec.data["status"] == "anchored":
            return rec.data
        result = anchor_batch(bid, rec.data["digest"])
        rec.data = {**rec.data, "status": "anchored", "chain": result}
        log(db, "proof.anchored", {"batch_id": bid, "block": result["block"]})
        return rec.data


from maas.integrations import register
register(app, get, temporal, log)

from maas.partners import register as register_partners
register_partners(app, temporal, log)
