"""Workflow decisions without a live bank or Temporal test-server download."""
import asyncio
from datetime import datetime, timedelta, timezone
from worker.main import BankPaymentWatch, workflow


def run_watch(monkeypatch, values):
    clock = [datetime(2026, 10, 25, tzinfo=timezone.utc)]
    calls = []
    async def execute(fn, oid, **kwargs):
        calls.append(oid)
        value = values[min(len(calls) - 1, len(values) - 1)]
        if isinstance(value, Exception):
            raise value
        return value
    async def sleep(duration):
        clock[0] += duration
    monkeypatch.setattr(workflow, "now", lambda: clock[0])
    monkeypatch.setattr(workflow, "execute_activity", execute)
    monkeypatch.setattr(workflow, "sleep", sleep)
    return asyncio.run(BankPaymentWatch().run("order-test")), calls, clock[0]


def test_watch_retries_outage_and_pending_until_exact_settlement(monkeypatch):
    result, calls, _ = run_watch(monkeypatch, [RuntimeError("temporary"), {"settled": False, "provider_status": "PDNG"}, {"settled": True, "provider_status": "ACSC"}])
    assert result["settled"] is True
    assert calls == ["order-test"] * 3


def test_watch_stops_on_refusal_without_confirming_payment(monkeypatch):
    result, calls, _ = run_watch(monkeypatch, [{"settled": False, "provider_status": "RJCT"}])
    assert not result["settled"]
    assert len(calls) == 1


def test_watch_is_bounded_and_requires_manual_reconciliation_after_window(monkeypatch):
    result, calls, end = run_watch(monkeypatch, [{"settled": False, "provider_status": "PDNG"}])
    assert not result["settled"]
    assert result["reason"] == "watch_window_expired_manual_reconciliation_required"
    assert len(calls) == 180
    assert end == datetime(2026, 10, 25, tzinfo=timezone.utc) + timedelta(minutes=15)
