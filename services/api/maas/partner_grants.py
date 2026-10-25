"""Short-lived grants bind MCP writes to one confirmed simulation operation."""
import os
from datetime import datetime, timedelta, timezone
import jwt

AUDIENCE = "maas-partner-tools"


def grant_for(operation):
    return jwt.encode({"sub": operation["id"], "actor": operation["actor"]["id"], "org": operation["org"], "partner": operation["partner"], "action": operation["action"], "fixture": operation["test_only"], "backend": operation["requested_backend"], "aud": AUDIENCE, "iss": "maas-local", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)}, os.environ["JWT_SECRET"], algorithm="HS256")


def read_grant(value):
    claims = jwt.decode(value, os.environ["JWT_SECRET"], algorithms=["HS256"], audience=AUDIENCE, issuer="maas-local", options={"require": ["sub", "actor", "org", "partner", "action", "fixture", "backend", "exp"]})
    if claims["partner"] not in ("bike", "parking") or claims["action"] not in ("reserve", "start", "finish", "cancel"):
        raise jwt.InvalidTokenError("Portée partenaire invalide")
    return claims
