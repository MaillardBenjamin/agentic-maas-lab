import os
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import text
from maas.db import Record, Session


def reserve(cents):
    """Conservative reservations, not invoice reconciliation or an absolute billing cap."""
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    with Session.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(62817)"))
        rid = "budget-" + month
        rec = db.get(Record, rid)
        used = rec.data["reserved_cents"] if rec else 0
        ceiling = int(Decimal(os.environ.get("AI_MONTHLY_BUDGET_EUR", "50")) * 100)
        if used + cents > ceiling:
            raise HTTPException(429, "Plafond mensuel de réservations IA atteint")
        value = {"month": month, "reserved_cents": used + cents, "limit_cents": ceiling}
        if rec:
            rec.data = value
        else:
            db.add(Record(id=rid, kind="budget", data=value))
        return value
