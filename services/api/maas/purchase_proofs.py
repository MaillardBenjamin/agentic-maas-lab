"""Transactional proof outbox. No network, signing key or chain on the sales path."""
from datetime import datetime, timezone
from maas.db import Record
from maas.domain import digest

STAGES = {"order.confirmed": "purchase", "payment.confirmed.simulated": "payment", "bridge.payment.confirmed": "payment", "order.fulfilled": "delivery", "refund.recorded.simulated": "regularization", "event.accepted": "usage"}


def source_snapshot(db, order, stage, source_id):
    if stage == "purchase":
        return {k: order.get(k) for k in ("id", "org", "traveler", "quote", "channel", "payment_mode", "created_at")}
    if stage == "payment":
        return {"order_id": order["id"], "payment_count": order["payment_count"], "paid_at": order.get("paid_at"), "mode": order.get("payment_mode"), "amount_cents": order["quote"]["total_cents"], "currency": order["quote"].get("currency", "EUR")}
    if stage == "delivery":
        return {"order_id": order["id"], "card": order.get("card")}
    record = db.get(Record, source_id)
    expected = "refund" if stage == "regularization" else "event"
    if not record or record.kind != expected:
        raise ValueError("Source de preuve absente")
    actual_order = record.data.get("order_id") if expected == "refund" else record.data.get("data", {}).get("order_id")
    if actual_order != order["id"]:
        raise ValueError("Source de preuve hors commande")
    return record.data


def record_lifecycle(db, action, payload, origin="business_transition"):
    stage = STAGES.get(action)
    if not stage or not payload.get("order_id"):
        return
    row = db.get(Record, payload["order_id"])
    if not row or row.kind != "order":
        raise ValueError("Commande de preuve absente")
    order = row.data
    source_id = payload.get("id") if stage == "regularization" else payload.get("event_id") if stage == "usage" else order["id"]
    snapshot = source_snapshot(db, order, stage, source_id)
    subject = digest({"org": order["org"], "order": order["id"]})
    bid = "purchase-proof-" + digest({"subject": subject, "stage": stage, "source": source_id})
    existing = db.get(Record, bid)
    if existing:
        if existing.data["snapshot_digest"] != digest(snapshot):
            raise ValueError("Preuve métier contradictoire")
        return existing.data
    at = datetime.now(timezone.utc).isoformat()
    manifest = {"schema_version": 2, "subject": subject, "origin": origin, "recorded_at": at, "events": [{"type": stage, "business_digest": digest(snapshot)}]}
    value = {"id": bid, "org": order["org"], "order_id": order["id"], "stage": stage, "source_id": source_id, "origin": origin, "recorded_at": at, "snapshot": snapshot, "snapshot_digest": digest(snapshot), "manifest": manifest, "digest": digest(manifest), "status": "pending"}
    db.add(Record(id=bid, kind="proof", data=value))
    return value


def check_source(db, proof, order):
    manifest = proof["manifest"]
    return (proof["org"] == order["org"] and proof["order_id"] == order["id"]
            and digest(proof["snapshot"]) == proof["snapshot_digest"]
            and digest(source_snapshot(db, order, proof["stage"], proof["source_id"])) == proof["snapshot_digest"]
            and manifest["subject"] == digest({"org": order["org"], "order": order["id"]})
            and manifest["origin"] == proof["origin"] and manifest["recorded_at"] == proof["recorded_at"]
            and manifest["events"] == [{"type": proof["stage"], "business_digest": proof["snapshot_digest"]}]
            and digest(manifest) == proof["digest"])
