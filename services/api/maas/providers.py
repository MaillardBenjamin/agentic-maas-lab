"""Supplier consultation: no purchase, booking or confirmation is required.

Only supplier data and the selected, accessible order's supplier lines leave
this facade. The signed scope never grants access to the execution endpoints.
"""
import jwt
from datetime import datetime, timezone
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from maas.db import Record, Session
from maas.organizations import CATALOG, organization, read_scope
from maas.security import USERS, access, principal
from maas.domain import quote


def inventory_id(tenant, provider):
    return "inventory-" + tenant + "-" + organization(provider, tenant)["org"]


class Consultation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)


def register(app, get, statement):
    @app.get("/api/organizations")
    def directory(user=Depends(principal)):
        return [o for o in CATALOG["organizations"] if user["org"] in o["distributors"]]

    @app.post("/api/provider-tools/{provider}/context")
    def context(provider: str, body: Consultation, user=Depends(principal), x_maas_provider_read: str = Header(default="")):
        try:
            scope = read_scope(x_maas_provider_read, "maas-provider-read", user)
            org = organization(provider, user["org"])
            if (scope.get("provider"), scope.get("provider_org"), scope.get("access")) != (provider, org["org"], "read"):
                raise ValueError()
        except (jwt.PyJWTError, KeyError, ValueError):
            raise HTTPException(403, "Délégation de consultation limitée à cette organisation requise")
        result = {"provider": provider, "provider_org": org["org"], "organization": org["name"], "version": CATALOG["version"], "currency": CATALOG["currency"], "products": [p for p in CATALOG["products"] if p["provider"] == provider], "distribution_contracts": [c for c in CATALOG["distribution_contracts"] if c["provider"] == provider and c["distributor_org"] == user["org"]], "simulation": True, "access": "read"}
        traveler = scope.get("traveler")
        if traveler:
            profile = USERS.get(traveler)
            if not profile or profile["role"] != "traveler" or profile["org"] != user["org"] or (user["role"] == "traveler" and traveler != user["id"]):
                raise HTTPException(403, "Profil hors périmètre")
            from zoneinfo import ZoneInfo
            on = scope.get("travel_date") or datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()
            result["price_preview"] = quote(profile, org["products"], scope.get("seller", "app"), on)
        with Session() as db:
            inventory = db.get(Record, inventory_id(user["org"], provider))
            result["availability"] = {"available_count": len(inventory.data["available"]), "observed_at": datetime.now(timezone.utc).isoformat(), "reservation_guaranteed": False, "source": "partner-inventory:" + org["org"]} if inventory else None
            oid = scope.get("order_id")
            if oid:
                order = get(db, oid, "order").data
                access(user, order)
                lines = [l for l in order["quote"]["lines"] if l.get("provider", l["product"]) == provider]
                if not lines:
                    raise HTTPException(403, "Organisation absente de la commande sélectionnée")
                result["order"] = {"id": oid, "state": order["state"], "lines": lines}
                result["bookings"] = [r.data for r in db.scalars(select(Record).where(Record.kind == "partner_booking")) if r.data["order_id"] == oid and r.data["partner"] == provider]
                kinds = {"transport": "maas.validation.accepted.v1", "bike": "maas.bike.ended.v1", "parking": "maas.parking.ended.v1"}
                result["events"] = [r.data for r in db.scalars(select(Record).where(Record.kind == "event")) if r.data["data"].get("order_id") == oid and r.data["type"] == kinds.get(provider)]
                result["statement"] = [line for line in statement(oid, user)["per_provider"] if line["provider"] == provider]
        try:
            from maas.knowledge import search_sources
            result["sources"] = search_sources(body.question, org["graph"])
        except Exception:
            raise HTTPException(503, "Sources de l’organisation indisponibles ; aucune explication inventée")
        return result
