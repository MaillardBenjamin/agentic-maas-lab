"""Explicit cloud entry points. Local demo remains runnable without secrets."""
import json
import asyncio
import os
import uuid
from datetime import datetime, timezone
from datetime import date
from decimal import Decimal

import httpx
from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from maas import bridge, agent_activity
from maas.budget import reserve
from maas.ai import chat_backend
from maas.db import Record, Session
from maas.domain import describe_quote, digest
from maas.security import access, principal, service
from maas.organizations import sign_scope
from maas.security import USERS
from maas.routing import normalized, resolve_plan
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError


class Chat(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    agent: str = Field(default="conversation", pattern=r"^(conversation|tariffs|sav|clearing|history)$")
    order_id: str | None = Field(default=None, max_length=80)
    traveler: str | None = Field(default=None, max_length=80)
    seller: str = Field(default="app", pattern=r"^(app|agency)$")
    travel_date: date | None = None


def register(app, get, temporal, log):
    @app.post("/api/chat")
    async def chat(body: Chat, request: Request, user=Depends(principal)):
        try:
            backend = chat_backend()
        except ValueError as exc:
            raise HTTPException(503, str(exc))
        if not backend:
            raise HTTPException(503, "IA désactivée. Activer AI_ENABLED et choisir AGENT_MODE=ollama ou openai.")
        message = body.message
        traveler = body.traveler or (user["id"] if user["role"] == "traveler" else None)
        preliminary = resolve_plan(message, tenant=user["org"])
        if preliminary["intent"] in ("history", "verification", "account"):
            import re
            names = {"lea": "lea", "alex": "adult", "adult": "adult"}
            named = {uid for name, uid in names.items() if re.search(r"\b" + name + r"\b", normalized(message))}
            if len(named) > 1:
                raise HTTPException(422, "Choisissez un seul voyageur pour la consultation")
            if named:
                requested = next(iter(named))
                if traveler and traveler != requested:
                    raise HTTPException(403, "Voyageur demandé hors du contexte sélectionné")
                traveler = requested
        if traveler and (traveler not in USERS or USERS[traveler]["role"] != "traveler" or USERS[traveler]["org"] != user["org"] or (user["role"] == "traveler" and traveler != user["id"])):
            raise HTTPException(403, "Voyageur hors périmètre")
        if body.seller == "agency" and user["role"] not in ("clerk", "supervisor", "demo"):
            raise HTTPException(403, "Vente agence réservée au conseiller")
        providers = []
        if body.order_id:
            with Session() as db:
                order = get(db, body.order_id, "order").data
                access(user, order)
                if traveler and traveler != order["traveler"]:
                    raise HTTPException(403, "Commande et voyageur incompatibles")
                traveler = order["traveler"]
                providers = [l.get("provider", l["product"]) for l in order["quote"]["lines"]]
            message = "Commande sélectionnée et accessible : " + body.order_id + ". Question : " + message
        plan = resolve_plan(body.message, {"order_id": body.order_id, "providers": providers}, user["org"])
        if plan.get("clarification"):
            return {"mode": "clarification_required", "text": plan["clarification"], "proposal": None, "evidence": {"a2a_agents": [], "mcp_tools": []}, "inference": False}
        if plan["target"] == "history" and not traveler:
            return {"mode": "clarification_required", "text": "Quel voyageur souhaitez-vous consulter ? Sélectionnez son profil dans le poste conseiller.", "proposal": None, "evidence": {"a2a_agents": [], "mcp_tools": []}, "inference": False}
        entry_agent = body.agent if body.agent == plan["target"] else "conversation"
        context = sign_scope("maas-coordination", user, traveler=traveler, seller=body.seller, travel_date=body.travel_date.isoformat() if body.travel_date else None, order_id=body.order_id, providers=providers, plan=plan)
        reservation = 100 if backend == "openai_via_agno" else 0
        value = reserve(reservation) if reservation else None
        with Session.begin() as db:
            log(db, "ai.reservation" if reservation else "ai.request.local", {"org": user["org"], "principal": user["id"], "reservation_cents": reservation, "mode": backend})
        rid = str(uuid.uuid4())
        payload = {"jsonrpc": "2.0", "id": rid, "method": "message/send", "params": {"message": {"messageId": rid, "role": "user", "parts": [{"kind": "text", "text": message}]}}}
        activity_id = agent_activity.start(user, "Dialogue avec les agents", backend)
        with agent_activity.exchange(activity_id, user, "A2A", "interface", entry_agent):
            try:
                async with httpx.AsyncClient(timeout=600 if backend == "ollama_local" else 180) as client:
                    result = await client.post("http://agents:8002/a2a/agents/" + entry_agent + "/v1/message:send", json=payload, headers={"Authorization": request.headers["Authorization"], "X-MaaS-Activity-ID": activity_id, "X-MaaS-Coordination": context})
                    result.raise_for_status()
                    task = result.json()["result"]
                if task["status"]["state"] != "completed" or result.headers.get("X-MaaS-Delegation-Failed") == "true":
                    raise ValueError("Agent non terminé")
                texts = [p["text"] for a in task.get("artifacts", []) for p in a.get("parts", []) if p.get("kind") == "text"]
                if not texts:
                    texts = [p["text"] for m in task.get("history", []) if m.get("role") == "agent" for p in m.get("parts", []) if p.get("kind") == "text"]
                if not texts:
                    raise ValueError("Réponse sans contenu")
                proposal = None
                if result.headers.get("X-MaaS-Proposal-ID"):
                    with Session() as db:
                        candidate = get(db, result.headers["X-MaaS-Proposal-ID"], "quote").data
                        if candidate["org"] != user["org"] or candidate["traveler"] != traveler or candidate["seller"] != body.seller:
                            raise ValueError("Proposition hors contexte")
                        proposal = candidate
                        texts = [describe_quote(proposal)]
                return {"activity_run_id": activity_id, "mode": backend, "protocol": "A2A", "text": "\n".join(texts), "proposal": proposal, "reservation_cents": reservation, "budget": value, "model": result.headers.get("X-MaaS-Model"), "provider": result.headers.get("X-MaaS-Provider"), "evidence": {"mcp_tools": [t for t in result.headers.get("X-MaaS-MCP-Tools", "").split(",") if t], "a2a_agents": [t for t in result.headers.get("X-MaaS-A2A-Agents", "").split(",") if t]}}
            except (httpx.HTTPError, ValueError, KeyError):
                raise HTTPException(502, "L’agent IA n’a pas abouti. Aucune action métier exécutée. Les éventuelles réservations cloud sont conservées.")

    @app.get("/api/budget")
    def budget(user=Depends(principal)):
        with Session() as db:
            rec = db.get(Record, "budget-" + datetime.now(timezone.utc).strftime("%Y-%m"))
            return rec.data if rec else {"reserved_cents": 0, "limit_cents": int(Decimal(os.environ.get("AI_MONTHLY_BUDGET_EUR", "50")) * 100), "note": "Réservations applicatives ; ne mesure pas la facture du fournisseur."}

    async def ensure_bank_watch(oid, value):
        with Session() as db:
            if get(db, oid, "order").data.get("channel") != "automate":
                return value
        try:
            client = await temporal()
            await client.start_workflow("BankPaymentWatch", oid, id="bank-watch-" + oid, task_queue="maas-ticketing", id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
        except WorkflowAlreadyStartedError:
            pass
        except Exception:
            raise HTTPException(503, "Lien bancaire conservé. Reprendre le suivi pour démarrer la surveillance Temporal, sans recréer le paiement.")
        return value

    @app.post("/api/orders/{oid}/bridge")
    async def start_bridge(oid: str, user=Depends(principal)):
        if not bridge.configured():
            raise HTTPException(503, "Bridge sandbox désactivé ou non configuré")
        with Session.begin() as db:
            rec = get(db, oid, "order", lock=True)
            access(user, rec.data)
            if rec.data["payment_mode"] != "bridge_sandbox" or rec.data["payment_count"]:
                raise HTTPException(409, "Commande non payable par Bridge")
            old = rec.data.get("bridge")
            if old:
                if old["status"] == "created":
                    return await ensure_bank_watch(oid, old)
                if old["status"] != "rejected":
                    raise HTTPException(409, "Création bancaire en cours ou incertaine : rapprochement requis, aucune relance automatique")
            try:
                payload = bridge.payment_payload(rec.data)
            except ValueError as exc:
                raise HTTPException(503, str(exc))
            rec.data = {**rec.data, "bridge": {"status": "creating"}}
        # Persist intent before network. Timeout/crash -> no second remote POST on retry.
        try:
            created = await asyncio.to_thread(bridge.create_payment, payload)
        except bridge.BridgeRequestRejected as exc:
            with Session.begin() as db:
                rec = get(db, oid, "order", lock=True)
                rec.data = {**rec.data, "bridge": {"status": "rejected", "http_status": exc.status_code, "error_code": exc.code}}
                log(db, "bridge.request.rejected", {"order_id": oid, "org": user["org"], "provider_http_status": exc.status_code, "provider_error_code": exc.code})
            raise HTTPException(502, {"message": "Bridge refuse la création ; aucun paiement créé", "provider_status": exc.status_code, "code": exc.code})
        except (httpx.HTTPError, ValueError):
            with Session.begin() as db:
                rec = get(db, oid, "order", lock=True)
                rec.data = {**rec.data, "bridge": {"status": "unknown"}, "state": "reconciliation_required"}
            raise HTTPException(502, "Réponse bancaire incertaine ; rapprocher côté Bridge avant de poursuivre")
        value = {"status": "created", **created, "mode": "bridge_sandbox"}
        with Session.begin() as db:
            rec = get(db, oid, "order", lock=True)
            rec.data = {**rec.data, "bridge": value}
            log(db, "bridge.request.created", {"order_id": oid, "org": user["org"]})
        return await ensure_bank_watch(oid, value)

    async def refresh_bank(oid):
        with Session() as db:
            value = get(db, oid, "order").data
            if value["payment_mode"] != "bridge_sandbox" or not value.get("bridge", {}).get("id"):
                raise HTTPException(409, "Demande Bridge absente")
        try:
            bank = await asyncio.to_thread(bridge.read_payment, value["bridge"]["id"], value["bridge"].get("resource_type", "payment_request"))
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, "Statut bancaire indisponible")
        settled = bridge.settled_for_order(bank, value)
        with Session.begin() as db:
            rec = get(db, oid, "order", lock=True)
            rec.data = {**rec.data, "bridge": {**rec.data["bridge"], "provider_status": bank.get("status"), "link_status": bank.get("link_status"), "checked_at": datetime.now(timezone.utc).isoformat(), "payment_request_id": bank.get("id")}}
        if settled:
            with Session.begin() as db:
                rec = get(db, oid, "order", lock=True)
                if not rec.data["payment_count"]:
                    rec.data = {**rec.data, "state": "paid", "payment_count": 1, "paid_at": datetime.now(timezone.utc).isoformat(), "bridge": {**rec.data["bridge"], "payment_request_id": bank.get("id")}}
                    log(db, "bridge.payment.confirmed", {"order_id": oid, "org": rec.data["org"]})
                needs_signal = rec.data["state"] != "fulfilled"
            if needs_signal:
                try:
                    client = await temporal()
                    await client.get_workflow_handle(oid).signal("payment_confirmed")
                except Exception:
                    # Completion may race with repeated polling. Persisted payment is never repeated.
                    with Session() as db:
                        done = get(db, oid, "order").data["state"] == "fulfilled"
                    if not done:
                        raise HTTPException(503, "Paiement bancaire confirmé et persisté ; répéter le contrôle pour reprendre Temporal")
        return {"mode": "bridge_sandbox", "provider_status": bank.get("status"), "settled": settled, "payment_request_id": bank.get("id")}

    @app.post("/internal/orders/{oid}/bridge/status", dependencies=[Depends(service)])
    async def watch_bank_status(oid: str):
        return await refresh_bank(oid)

    @app.post("/api/orders/{oid}/bridge/status")
    async def bank_status(oid: str, user=Depends(principal)):
        with Session() as db:
            access(user, get(db, oid, "order").data)
        return await refresh_bank(oid)

    @app.post("/api/webhooks/bridge")
    async def webhook(request: Request, bridgeapi_signature: str = Header(default="")):
        raw = await request.body()
        if len(raw) > 100000:
            raise HTTPException(413)
        if not bridge.verify_signature(raw, bridgeapi_signature, os.environ.get("BRIDGE_WEBHOOK_SECRET", "")):
            raise HTTPException(401, "Signature Bridge invalide")
        try:
            payload = json.loads(raw)
            content = payload["content"]
            if payload.get("type") not in ("payment.transaction.created", "payment.transaction.updated", "payment.link.updated") or not isinstance(content, dict):
                raise ValueError("Événement inattendu")
        except (ValueError, KeyError, TypeError):
            raise HTTPException(422, "Notification non prise en charge")
        with Session() as db:
            order = next((r.data for r in db.scalars(select(Record).where(Record.kind == "order")) if bridge.notification_matches(r.data, content)), None)
        if not order:
            raise HTTPException(404, "Demande bancaire inconnue")
        # Re-read provider status. Replayed notification cannot create a second effect.
        return await refresh_bank(order["id"])
