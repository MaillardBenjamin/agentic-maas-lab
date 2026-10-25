import os
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from fastapi import Depends, Header, HTTPException

USERS = {
    "lea": {"id": "lea", "name": "Léa · étudiante fictive", "role": "traveler", "org": "alize", "birth_date": "2004-06-12", "student_verified": True, "student_until": "2027-08-31"},
    "adult": {"id": "adult", "name": "Alex · adulte fictif", "role": "traveler", "org": "alize", "birth_date": "1980-01-01", "student_verified": False},
    "clerk": {"id": "clerk", "name": "Camille · conseiller", "role": "clerk", "org": "alize"},
    "supervisor": {"id": "supervisor", "name": "Sam · superviseur", "role": "supervisor", "org": "alize"},
    "demo": {"id": "demo", "name": "Console de démonstration", "role": "demo", "org": "alize"},
}


def secret():
    return os.environ.get("JWT_SECRET", "local-demo-change-before-exposure-0123456789")


def token(user):
    return jwt.encode({**user, "exp": datetime.now(timezone.utc) + timedelta(hours=2), "aud": "maas-demo", "iss": "maas-local"}, secret(), algorithm="HS256")


def principal(authorization: str = Header(default="")):
    try:
        scheme, value = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise ValueError()
        return jwt.decode(value, secret(), algorithms=["HS256"], audience="maas-demo", issuer="maas-local")
    except (ValueError, jwt.PyJWTError):
        raise HTTPException(401, "Session locale requise")


def service(x_service_token: str = Header(default="")):
    import secrets
    if not secrets.compare_digest(x_service_token, os.environ.get("SERVICE_TOKEN", "local-services-only-0123456789")):
        raise HTTPException(403, "Service non autorisé")


def access(user, order):
    if user["org"] != order["org"] or (user["role"] == "traveler" and user["id"] != order["traveler"]):
        raise HTTPException(403, "Commande hors périmètre")


def authorize(user, action, order, amount=0):
    access(user, order)
    payload = {"principal": user, "action": action, "org": order["org"], "amount_cents": amount}
    try:
        result = httpx.post(os.environ.get("OPA_URL", "http://opa:8181") + "/v1/data/maas/allow", json={"input": payload}, timeout=3)
        result.raise_for_status()
        allowed = result.json().get("result") is True
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "OPA indisponible : action sensible refusée")
    if not allowed:
        raise HTTPException(403, "Action refusée par OPA")
