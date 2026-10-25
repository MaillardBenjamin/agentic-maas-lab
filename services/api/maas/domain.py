import hashlib
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

CATALOG = json.loads(Path("fixtures/catalog.json").read_text())


def canonical(value):
    # All proof payloads use integers, strings, booleans and UTC strings (no floats).
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def percentage(amount: int, bps: int) -> int:
    return int((Decimal(amount) * Decimal(bps) / 10000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def age_on(birth: str, on: date):
    dob = date.fromisoformat(birth)
    if dob > on:
        raise ValueError("Date de naissance postérieure au voyage")
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def quote(profile: dict, products: list[str], seller: str, travel_date: str):
    if seller not in CATALOG["sellers"]:
        raise ValueError("Vendeur inconnu")
    if not products or len(set(products)) != len(products):
        raise ValueError("Produits vides ou répétés")
    on = date.fromisoformat(travel_date)
    lines = []
    for pid in products:
        product = next((p for p in CATALOG["products"] if p["id"] == pid), None)
        if not product:
            raise ValueError("Produit inconnu")
        amount = product["price_cents"]
        rule = "standard"
        if pid == "transport":
            discounts = [(0, "standard")]
            if age_on(profile["birth_date"], on) < product["young_under"]:
                discounts.append((product["young_bps"], "moins de 26 ans"))
            if profile.get("student_verified") and date.fromisoformat(profile["student_until"]) >= on:
                discounts.append((product["student_bps"], "étudiant vérifié"))
            bps, rule = max(discounts)
            amount -= percentage(amount, bps)
        lines.append({"product": pid, "name": product["name"], "actor": product["actor"], "amount_cents": amount, "rule": rule, "terms": dict(product), "source": "tariff-1" if pid == "transport" else f"{pid}-1"})
    return {"version": CATALOG["version"], "currency": "EUR", "seller": seller, "commission_bps": CATALOG["sellers"][seller]["commission_bps"], "travel_date": travel_date, "lines": lines, "total_cents": sum(l["amount_cents"] for l in lines)}


def bike_price(seconds: int, tariff: dict | None = None) -> int:
    if seconds < 0:
        raise ValueError("Durée négative")
    tariff = tariff or next(p for p in CATALOG["products"] if p["id"] == "bike")
    return min(tariff["cap_cents"], tariff["unlock_cents"] + ((seconds + 59) // 60) * tariff["minute_cents"])


def settlement(order: dict, refunded: int, bike_cents: int = 0):
    paid = order["quote"]["total_cents"] if order.get("payment_count") == 1 else 0
    if not 0 <= refunded <= paid:
        raise ValueError("Régularisation supérieure au montant payé")
    net = paid - refunded
    commission = percentage(net, order["quote"]["commission_bps"])
    bike_commission = percentage(bike_cents, order["quote"]["commission_bps"])
    return {"prepaid_cents": paid, "refund_cents": refunded, "net_prepaid_cents": net, "seller_commission_cents": commission, "operators_cents": net - commission, "bike_due_cents": bike_cents, "bike_commission_pending_cents": bike_commission, "bike_operator_pending_cents": bike_cents - bike_commission, "currency": "EUR", "note": "Vélo : créance simulée non encore encaissée ; aucun reversement bancaire réel."}
