"""One ledger for console deliveries and partner CloudEvents (same transaction)."""
from datetime import datetime, timezone
from fastapi import HTTPException
from maas.db import Record
from maas.domain import digest

SOURCES = {
    "maas.validation.accepted.v1": {"urn:manufacturer:x", "urn:manufacturer:y"},
    "maas.bike.ended.v1": {"urn:partner:bike"},
    "maas.parking.ended.v1": {"urn:partner:parking"},
}
PRODUCTS = {"maas.validation.accepted.v1": "transport", "maas.bike.ended.v1": "bike", "maas.parking.ended.v1": "parking"}


def store_event(db, body, order, org, log):
    body = {**body, "time": datetime.fromisoformat(body["time"].replace("Z", "+00:00")).isoformat().replace("+00:00", "Z")}
    if body.get("specversion", "1.0") != "1.0" or body.get("source") not in SOURCES.get(body.get("type"), set()):
        raise HTTPException(422, "Type, source ou version CloudEvents invalide")
    data = body["data"]
    if body["type"] == "maas.bike.ended.v1" and (type(data.get("seconds")) is not int or data["seconds"] < 0):
        raise HTTPException(422, "Durée invalide")
    passage = data.get("passage_id")
    if not isinstance(passage, str) or not passage:
        raise HTTPException(422, "Identité métier passage_id requise")
    if order["state"] != "fulfilled":
        raise HTTPException(409, "Droit non émis")
    if PRODUCTS[body["type"]] not in [line["product"] for line in order["quote"]["lines"]]:
        raise HTTPException(409, "Produit absent de la commande")
    key = "event-" + digest({"org": org, "order": order["id"], "passage": passage, "type": body["type"]})
    delivery_key = "delivery-" + digest({"org": org, "source": body["source"], "id": body["id"]})
    fingerprint = digest({"order_id": order["id"], "passage_id": passage, "type": body["type"], "time": body["time"], "seconds": data.get("seconds")})
    delivery = db.get(Record, delivery_key)
    if delivery:
        if delivery.data["event_key"] != key or delivery.data["business_digest"] != fingerprint:
            raise HTTPException(409, "Identifiant CloudEvents déjà lié à un autre événement")
        return {"accepted": False, "duplicate": True, "id": key}
    old = db.get(Record, key)
    if old and old.data["business_digest"] != fingerprint:
        raise HTTPException(409, "Événement contradictoire : à rapprocher")
    db.add(Record(id=delivery_key, kind="delivery", data={"event_key": key, "business_digest": fingerprint}))
    if old:
        return {"accepted": False, "duplicate": True, "id": key}
    db.add(Record(id=key, kind="event", data={**body, "received_at": datetime.now(timezone.utc).isoformat(), "org": org, "business_digest": fingerprint}))
    log(db, "event.accepted", {"order_id": order["id"], "org": org, "event_id": key, "type": body["type"]})
    return {"accepted": True, "id": key}
