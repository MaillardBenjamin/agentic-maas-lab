"""Published organization directory and signed, read-only delegation scopes.

The distributor tenant (org) and the supplier organization (provider_org) are
different identities, including in this local simulation with a shared issuer.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

CATALOG = json.loads(Path("fixtures/catalog.json").read_text())


def organization(provider, tenant="alize"):
    value = next((o for o in CATALOG["organizations"] if o["id"] == provider), None)
    if not value or tenant not in value["distributors"]:
        raise ValueError("Organisation inconnue ou hors accord de distribution")
    return value


def supplier(product):
    value = next((o for o in CATALOG["organizations"] if product in o["products"]), None)
    if value is None:
        raise ValueError("Produit sans organisation fournisseur publiée")
    return value


def sign_scope(audience, user, **scope):
    return jwt.encode({**scope, "actor": user["id"], "org": user["org"], "role": user["role"],
                       "aud": audience, "iss": "maas-local", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
                      os.environ["JWT_SECRET"], algorithm="HS256")


def read_scope(value, audience, user):
    claims = jwt.decode(value, os.environ["JWT_SECRET"], algorithms=["HS256"], audience=audience, issuer="maas-local",
                        options={"require": ["actor", "org", "role", "exp"]})
    if (claims["actor"], claims["org"], claims["role"]) != (user["id"], user["org"], user["role"]):
        raise jwt.InvalidTokenError("Délégation liée à une autre identité")
    return claims


def provider_scope(user, provider, order_id=None, traveler=None, seller="app", travel_date=None):
    value = organization(provider, user["org"])
    return sign_scope("maas-provider-read", user, provider=provider, provider_org=value["org"], order_id=order_id, traveler=traveler, seller=seller, travel_date=travel_date, access="read")
