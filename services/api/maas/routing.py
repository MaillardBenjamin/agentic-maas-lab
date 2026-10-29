"""Conservative, explicit request scope shared by API and agent runtime."""
import re
import unicodedata
try:
    from maas.organizations import CATALOG, organization
except ModuleNotFoundError:  # Shared by the standalone agent image.
    from organizations import CATALOG, organization

COORDINATORS = {"tariff": "tariffs", "offer": "mobility", "availability": "mobility", "sav": "sav", "clearing": "clearing", "history": "history", "verification": "history", "account": "history"}


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def resolve_plan(question, context=None, tenant="alize"):
    context = context or {}
    text = normalized(question)
    def has(pattern):
        return bool(re.search(pattern, text))
    history = has(r"\b(achats?|historique|commandes|compte mobilite|echeances|factures|mensualites|achete|achetes|achetee|achetees)\b")
    proof = has(r"\b(blockchain|preuves?|ancrage|integrite)\b")
    if has(r"\b(compte mobilite|mon compte|mes titres|mes abonnements|echeances|factures|mensualites|mon abonnement)\b"):
        intent = "account"
    elif proof:
        intent = "verification"
    elif history:
        intent = "history"
    elif has(r"\b(commissions?|repartition|reversements?)\b"):
        intent = "clearing"
    elif has(r"\b(sav|incident|panne|refus\w*|rembours\w*|regularis\w*|restitution)\b") or has(r"ne.*(?:deverrouille|fonctionne)"):
        intent = "sav"
    elif has(r"\b(prepar\w*|proposition|devis|acheter|reserv\w*)\b"):
        intent = "offer"
    elif has(r"\b(disponib\w*|places?)\b"):
        intent = "availability"
    elif has(r"\b(tarifs?|abonnement|post.paiement|abt|prix|coute|cout|combien|etudiant)\b"):
        intent = "tariff"
    else:
        return {"intent": "unknown", "providers": [], "clarification": "Souhaitez-vous consulter vos achats, un tarif, une disponibilité, un dossier SAV ou une répartition ?"}
    selected, excluded_providers = [], set()
    aliases = {"transport": r"\b(transport\w*|abt|abonnement|post.paiement|reseau|titre\w*|etudiant)\b", "parking": r"\b(parking\w*|stationnement)\b|p\+r", "bike": r"\b(velos?|bike)\b"}
    for org in CATALOG["organizations"]:
        alias = aliases.get(org["id"], r"\b" + re.escape(normalized(org["id"])) + r"\b")
        excluded = has(r"\b(?:sans|sauf|pas|ni|excluant)\s+(?:(?:de|du|le|la|les|des|d|l)\s+)*?(?:" + alias + r")")
        if excluded:
            excluded_providers.add(org["id"])
        if has(alias) and not excluded:
            selected.append(org["id"])
    if intent in ("history", "verification", "account"):
        return {"intent": intent, "target": "history", "providers": [], "question": question}
    # Broader scope requires an explicit collective request, never an empty model list.
    collective = has(r"\b(tous|toutes|ensemble|par fournisseur|par organisation|ma commande|cette commande|commande selectionnee)\b")
    if not selected and collective:
        selected = list(context.get("providers") or [])
        if not selected and has(r"\b(tous|toutes)\b"):
            selected = [o["id"] for o in CATALOG["organizations"] if tenant in o["distributors"]]
    if not selected and len(context.get("providers", [])) == 1:
        selected = context["providers"][:]
    selected = [p for p in selected if p not in excluded_providers]
    plan = {"intent": intent, "target": COORDINATORS[intent], "providers": selected, "question": question}
    if not selected:
        plan["clarification"] = "Quel service est concerné : transport, parking ou vélo ?"
    for provider in selected:
        org = organization(provider, tenant)
        if intent not in org["capabilities"]:
            plan["clarification"] = "Cette organisation ne propose pas la compétence demandée. Précisez le service et votre besoin."
        if intent in ("sav", "clearing") and context.get("order_id") and provider not in context.get("providers", []):
            plan["clarification"] = "Ce service ne figure pas dans la commande sélectionnée. Choisissez la commande concernée."
    return plan


def validate_selection(plan, coordinator, requested, tenant):
    if plan.get("clarification") or not plan.get("providers"):
        raise ValueError("Service à préciser avant toute délégation")
    if coordinator != plan.get("target"):
        raise ValueError("Compétence du coordinateur incompatible avec la demande")
    expected = plan["providers"]
    if any(p not in expected for p in requested):
        raise ValueError("Fournisseur non concerné par la demande")
    for provider in expected:
        if plan["intent"] not in organization(provider, tenant)["capabilities"]:
            raise ValueError("Compétence fournisseur incompatible")
    return list(dict.fromkeys(expected))
