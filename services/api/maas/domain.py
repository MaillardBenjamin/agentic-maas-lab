import hashlib
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from maas.organizations import CATALOG, supplier


def canonical(value):
    # All proof payloads use integers, strings, booleans and UTC strings (no floats).
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def percentage(amount: int, bps: int) -> int:
    return int((Decimal(amount) * Decimal(bps) / 10000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def money(cents):
    return f"{cents // 100},{cents % 100:02d} €"


def describe_quote(value):
    """Customer-facing monetary facts come from the accepted quote structure."""
    lines = ["Proposition pour le " + date.fromisoformat(value["travel_date"]).strftime("%d/%m/%Y") + " :"]
    for line in value["lines"]:
        if line["product"] == "bike":
            terms = line["terms"]
            price = f"après usage · {money(terms['unlock_cents'])} + {money(terms['minute_cents'])}/minute commencée, plafond {money(terms['cap_cents'])}"
        else:
            price = money(line["amount_cents"])
        lines.append(f"• {line['name']} : {price}. Source : {line['source']}.")
    lines.extend(["", "À payer maintenant : " + money(value["total_cents"]) + ".", "Examinez les produits, la date et le montant dans l’écran avant de confirmer. Aucune réservation ni commande n’a été effectuée."])
    return "\n".join(lines)


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
        provider = supplier(pid)
        contract = next((c for c in CATALOG["distribution_contracts"] if c["provider"] == provider["id"] and c["seller"] == seller and c["distributor_org"] == profile.get("org", "alize")), None)
        if contract is None:
            raise ValueError("Accord de distribution absent pour ce fournisseur")
        lines.append({"product": pid, "name": product["name"], "actor": provider["org"], "provider": provider["id"], "provider_org": provider["org"], "amount_cents": amount, "rule": rule, "terms": dict(product), "source": product["source"], "distribution_contract": dict(contract)})
    return {"version": CATALOG["version"], "currency": "EUR", "seller": seller, "commission_bps": CATALOG["sellers"][seller]["commission_bps"], "travel_date": travel_date, "lines": lines, "total_cents": sum(l["amount_cents"] for l in lines)}


def bike_price(seconds: int, tariff: dict | None = None) -> int:
    if seconds < 0:
        raise ValueError("Durée négative")
    tariff = tariff or next(p for p in CATALOG["products"] if p["id"] == "bike")
    return min(tariff["cap_cents"], tariff["unlock_cents"] + ((seconds + 59) // 60) * tariff["minute_cents"])


def allocate_refund(lines, amount, previous=None, product=None):
    """Allocate cents to order lines, bounded by their remaining paid amounts."""
    previous = previous or {}
    remaining = {l["product"]: l["amount_cents"] - previous.get(l["product"], 0) for l in lines if product is None or l["product"] == product}
    total = sum(remaining.values())
    if amount < 0 or amount > total or any(v < 0 for v in remaining.values()):
        raise ValueError("Régularisation supérieure au montant restant des lignes")
    if not total:
        return {}
    values = {p: amount * v // total for p, v in remaining.items()}
    for p in sorted(remaining, key=lambda p: (-(amount * remaining[p] % total), p))[:amount - sum(values.values())]:
        values[p] += 1
    return values


def settlement(order: dict, refunded: int, bike_cents: int = 0):
    paid = order["quote"]["total_cents"] if order.get("payment_count") == 1 else 0
    if not 0 <= refunded <= paid:
        raise ValueError("Régularisation supérieure au montant payé")
    net = paid - refunded
    lines = order["quote"].get("lines", [])
    refunds = order.get("refund_allocations")
    if refunds is None:
        refunds = allocate_refund(lines, refunded) if lines else {}
    if lines and sum(refunds.values()) != refunded:
        raise ValueError("Répartition de régularisation incohérente")
    per_provider = []
    for line in lines:
        contract = line.get("distribution_contract", {})
        bps = contract.get("commission_bps", order["quote"]["commission_bps"])
        line_paid = line["amount_cents"] if paid else 0
        refund = refunds.get(line["product"], 0)
        if not 0 <= refund <= line_paid:
            raise ValueError("Régularisation de ligne incohérente")
        line_net = line_paid - refund
        due = bike_cents if line["product"] == "bike" else 0
        fee, pending = percentage(line_net, bps), percentage(due, bps)
        per_provider.append({"product": line["product"], "provider": line.get("provider", line["product"]), "provider_org": line.get("provider_org", supplier(line["product"])["org"]), "contract": contract, "prepaid_cents": line_paid, "refund_cents": refund, "net_prepaid_cents": line_net, "seller_commission_cents": fee, "operator_cents": line_net - fee, "postpaid_due_cents": due, "commission_pending_cents": pending, "operator_pending_cents": due - pending})
    # Old orders did not include a bike line in certain test/legacy snapshots.
    commission = sum(v["seller_commission_cents"] for v in per_provider) if lines else percentage(net, order["quote"]["commission_bps"])
    bike_line = next((v for v in per_provider if v["product"] == "bike"), None)
    bike_commission = bike_line["commission_pending_cents"] if bike_line else percentage(bike_cents, order["quote"]["commission_bps"])
    return {"prepaid_cents": paid, "refund_cents": refunded, "net_prepaid_cents": net, "seller_commission_cents": commission, "operators_cents": net - commission, "bike_due_cents": bike_cents, "bike_commission_pending_cents": bike_commission, "bike_operator_pending_cents": bike_cents - bike_commission, "per_provider": per_provider, "currency": "EUR", "note": "Vélo : créance simulée non encore encaissée ; aucun reversement bancaire réel."}
