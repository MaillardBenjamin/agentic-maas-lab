from datetime import date

import pytest

from maas.domain import age_on, bike_price, digest, quote, settlement
from maas.security import USERS


def test_student_discount_not_stacked():
    result = quote(USERS["lea"], ["transport", "parking", "bike"], "agency", "2026-10-24")
    assert result["total_cents"] == 1200
    assert result["lines"][0]["amount_cents"] == 700
    assert result["lines"][0]["rule"] == "étudiant vérifié"


def test_expired_student_only_age_discount():
    profile = {**USERS["lea"], "student_until": "2025-01-01"}
    assert quote(profile, ["transport"], "app", "2026-10-24")["total_cents"] == 800


def test_age_on_travel_date():
    profile = {"birth_date": "2000-10-25", "student_verified": False}
    assert quote(profile, ["transport"], "app", "2026-10-24")["total_cents"] == 800
    assert quote(profile, ["transport"], "app", "2026-10-25")["total_cents"] == 1000


def test_standard_price():
    assert quote(USERS["adult"], ["transport"], "app", "2026-10-24")["total_cents"] == 1000


@pytest.mark.parametrize("products,seller", [([], "app"), (["fake"], "app"), (["transport", "transport"], "app"), (["transport"], "fake")])
def test_invalid_catalog_request(products, seller):
    with pytest.raises(ValueError):
        quote(USERS["lea"], products, seller, "2026-10-24")


@pytest.mark.parametrize("seconds,expected", [(0, 100), (1, 120), (60, 120), (61, 140), (1200, 500), (99999, 500)])
def test_rental_duration_rounding_and_cap(seconds, expected):
    assert bike_price(seconds) == expected


def test_invalid_duration():
    with pytest.raises(ValueError):
        bike_price(-1)


def test_postpaid_uses_accepted_tariff_terms():
    assert bike_price(600, {"unlock_cents": 80, "minute_cents": 10, "cap_cents": 300}) == 180
    assert bike_price(99999, {"unlock_cents": 80, "minute_cents": 10, "cap_cents": 300}) == 300


def test_distribution_after_refund():
    order = {"quote": quote(USERS["lea"], ["transport", "parking"], "agency", "2026-10-24"), "payment_count": 1}
    result = settlement(order, 200, 300)
    assert result["net_prepaid_cents"] == 1000
    assert result["seller_commission_cents"] == 50
    assert result["operators_cents"] == 950
    assert result["bike_commission_pending_cents"] == 15
    assert result["bike_operator_pending_cents"] == 285
    assert result["net_prepaid_cents"] == result["seller_commission_cents"] + result["operators_cents"]


def test_seller_changes_commission_not_passenger_price():
    agency = quote(USERS["lea"], ["transport"], "agency", "2026-10-24")
    app = quote(USERS["lea"], ["transport"], "app", "2026-10-24")
    assert agency["total_cents"] == app["total_cents"] == 700
    assert settlement({"quote": agency, "payment_count": 1}, 0)["seller_commission_cents"] == 35
    assert settlement({"quote": app, "payment_count": 1}, 0)["seller_commission_cents"] == 14


def test_cannot_over_refund():
    with pytest.raises(ValueError):
        settlement({"quote": {"total_cents": 100}}, 101)


def test_unpaid_order_creates_no_collection_or_commission():
    result = settlement({"quote": {"total_cents": 1200, "commission_bps": 500}, "payment_count": 0}, 0)
    assert result["prepaid_cents"] == result["seller_commission_cents"] == result["operators_cents"] == 0


def test_proof_digest_order_independent_and_tamper_sensitive():
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})
    assert digest({"a": 1}) != digest({"a": 2})
