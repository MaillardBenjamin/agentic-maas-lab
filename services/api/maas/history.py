"""Scoped purchase history and fresh proof verification, exposed read-only to agents."""
from datetime import datetime, timezone
import jwt
from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy import select, func
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from maas.db import Record, Session
from maas.organizations import read_scope
from maas.security import USERS, access, principal, service
from maas.purchase_proofs import check_source
from maas.proofs import verify_record


def selected_traveler(user, signed, requested=None):
    try:
        scope = read_scope(signed, "maas-coordination", user)
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(403, "Contexte de consultation signé requis")
    if user["role"] not in ("traveler", "clerk", "supervisor", "demo"):
        raise HTTPException(403, "Profil non autorisé")
    bound = user["id"] if user["role"] == "traveler" else scope.get("traveler")
    if requested and bound and requested != bound:
        raise HTTPException(403, "Voyageur hors du contexte sélectionné")
    uid = bound or requested
    profile = USERS.get(uid)
    if not profile or profile["role"] != "traveler" or profile["org"] != user["org"]:
        raise HTTPException(422, "Sélectionnez un voyageur autorisé avant de consulter ses achats")
    return uid


def register(app, get, temporal):
    @app.get("/api/assistant/purchases")
    def purchases(traveler_id: str | None = None, limit: int = Query(10, ge=1, le=20), offset: int = Query(0, ge=0, le=10000), user=Depends(principal), x_maas_coordination: str = Header(default="")):
        uid = selected_traveler(user, x_maas_coordination, traveler_id)
        with Session() as db:
            condition = (Record.kind == "order", Record.data["org"].as_string() == user["org"], Record.data["traveler"].as_string() == uid)
            total = db.scalar(select(func.count()).select_from(Record).where(*condition))
            orders = db.scalars(select(Record).where(*condition).order_by(Record.created_at.desc(), Record.id.desc()).offset(offset).limit(limit))
            rows = []
            for row in orders:
                o = row.data
                proofs = [p.data for p in db.scalars(select(Record).where(Record.kind == "proof")) if p.data.get("order_id") == o["id"] and p.data.get("org") == user["org"]]
                rows.append({"account_id": o.get("account_id"), "id": o["id"], "created_at": o["created_at"], "state": o["state"], "products": [{"id": l["product"], "name": l["name"]} for l in o["quote"]["lines"]], "total_cents": o["quote"]["total_cents"], "currency": o["quote"].get("currency", "EUR"), "payment_confirmed": o.get("payment_count") == 1, "payment_mode": o.get("payment_mode"), "proof_status": "verification_required" if proofs else "not_available"})
        return {"traveler_id": uid, "total": total, "offset": offset, "limit": limit, "has_more": offset + len(rows) < total, "purchases": rows, "note": "Une commande en attente de paiement n’est pas un achat payé. Le statut des preuves exige une vérification dédiée ; un ancrage atteste un contenu enregistré, pas un encaissement bancaire."}

    def scoped_order(db, oid, user, signed):
        uid = selected_traveler(user, signed)
        order = get(db, oid, "order").data
        access(user, order)
        if order["traveler"] != uid:
            raise HTTPException(403, "Commande hors voyageur sélectionné")
        return order

    @app.get("/api/assistant/purchases/{oid}")
    def purchase_detail(oid: str, user=Depends(principal), x_maas_coordination: str = Header(default="")):
        with Session() as db:
            o = scoped_order(db, oid, user, x_maas_coordination)
            return {k: o.get(k) for k in ("id", "account_id", "created_at", "state", "quote", "payment_count", "payment_mode", "paid_at", "refund_cents")}

    @app.get("/api/assistant/purchases/{oid}/proofs")
    def purchase_proofs(oid: str, user=Depends(principal), x_maas_coordination: str = Header(default="")):
        with Session() as db:
            order = scoped_order(db, oid, user, x_maas_coordination)
            records = [r.data for r in db.scalars(select(Record).where(Record.kind == "proof")) if r.data.get("order_id") == oid and r.data.get("org") == user["org"]]
            checks = []
            for proof in records:
                try:
                    intact = check_source(db, proof, order)
                except (KeyError, ValueError):
                    intact = False
                checks.append(verify_record(proof) if intact else {"id": proof["id"], "stage": proof.get("stage"), "status": "data_mismatch"})
            required = {"purchase"} | ({"payment"} if order.get("payment_count") else set()) | ({"delivery"} if order.get("card") else set()) | ({"regularization"} if order.get("refund_cents") else set())
            expected = {(s, oid) for s in required if s != "regularization"}
            for row in db.scalars(select(Record).where(Record.kind.in_(["refund", "event"]))):
                linked = row.data.get("order_id") if row.kind == "refund" else row.data.get("data", {}).get("order_id")
                if linked == oid:
                    expected.add(("regularization" if row.kind == "refund" else "usage", row.id))
            missing = expected - {(p["stage"], p["source_id"]) for p in records}
            present = {p["stage"] for p in records}
            statuses = {p["status"] for p in checks}
            status = next((s for s in ("data_mismatch", "invalid", "chain_unavailable", "deployment_changed", "failed", "pending", "not_anchored") if s in statuses), "verified" if not missing and required <= present and checks else "not_available")
        return {"order_id": oid, "status": status, "missing_stages": sorted((required - present) | {s for s, _ in missing}), "missing_sources": [{"stage": s, "id": i} for s, i in sorted(missing)], "proofs": checks, "scope": "integrity_of_recorded_content", "note": "La confirmation de paiement vient du service métier et du connecteur bancaire ; la chaîne atteste l’intégrité du contenu ancré. Les données personnelles et détails d’achat restent hors chaîne."}

    @app.post("/internal/proofs/dispatch", dependencies=[Depends(service)])
    async def dispatch():
        with Session() as db:
            pending = sorted([r.data for r in db.scalars(select(Record).where(Record.kind == "proof")) if r.data.get("stage") and r.data["status"] == "pending"], key=lambda p: p.get("last_dispatch_at", ""))[:20]
        if not pending:
            return {"dispatched": 0}
        client = await temporal()
        for proof in pending:
            failed = False
            try:
                await client.start_workflow("ProofAnchoring", proof["id"], id=proof["id"], task_queue="maas-ticketing", id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
            except WorkflowAlreadyStartedError:
                state = await client.get_workflow_handle(proof["id"]).describe()
                failed = state.status.name in ("FAILED", "CANCELED", "TERMINATED", "TIMED_OUT")
            with Session.begin() as db:
                rec = get(db, proof["id"], "proof", lock=True)
                if rec.data["status"] == "pending":
                    rec.data = {**rec.data, "last_dispatch_at": datetime.now(timezone.utc).isoformat(), "status": "failed" if failed else "pending"}
        return {"dispatched": len(pending)}
