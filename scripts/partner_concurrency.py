"""PostgreSQL concurrency, real A2A/MCP, deterministic model double only."""
import asyncio
import json
import os
import uuid
from pathlib import Path
from temporalio.client import Client
from maas.api import log
from maas.db import Session
from maas.partners import PartnerRequest, prepare_operation
from maas.security import USERS
from smoke import call, login, wait

lea = login("lea")
prefix = "concurrency-" + uuid.uuid4().hex


def new_order():
    q = call("/api/quotes", lea, {"products": ["bike", "parking"]})
    order = call("/api/orders", lea, {"quote_id": q["id"], "idempotency_key": prefix + uuid.uuid4().hex[:6]})
    call("/api/demo/orders/" + order["id"] + "/pay", lea, {})
    wait(order["id"], "fulfilled", lea)
    return order["id"]


def prepare(oid, partner, action, key):
    with Session.begin() as db:
        return prepare_operation(db, oid, PartnerRequest(partner=partner, action=action, confirmed=True, idempotency_key=key), USERS["lea"], log, test_only=True)


async def start(op):
    client = await Client.connect(os.environ["TEMPORAL_ADDRESS"])
    handle = await client.start_workflow("PartnerInteraction", {"operation_id": op["id"], "fixture": True}, id=op["id"], task_queue="maas-ticketing")
    return await handle.result()


async def main():
    orders = [new_order() for _ in range(3)]
    assert call("/api/orders/" + orders[0] + "/partners", lea)["availability"]["bike"] == 2, "Deux vélos libres requis pour ce test"
    operations = [prepare(oid, "bike", "reserve", prefix + str(i)) for i, oid in enumerate(orders)]
    results = await asyncio.gather(*(start(op) for op in operations))
    assert sorted(x["status"] for x in results) == ["completed", "completed", "failed"], results
    active = []
    for oid in orders:
        state = call("/api/orders/" + oid + "/partners", lea)
        if state["bookings"]:
            active.append((oid, state["bookings"][0]["asset_id"]))
    assert len(active) == len({asset for _, asset in active}) == 2
    await asyncio.gather(*(start(prepare(oid, "bike", "cancel", prefix + "-cancel-" + str(i))) for i, (oid, _) in enumerate(active)))
    assert call("/api/orders/" + orders[0] + "/partners", lea)["availability"]["bike"] == 2
    refused = next(op for op, result in zip(operations, results) if result["status"] == "failed")
    call("/api/partner-operations/" + refused["id"] + "/resume", lea, {"confirmed": False}, 422)
    call("/api/partner-operations/" + refused["id"] + "/resume", login("adult"), {"confirmed": True}, 403)
    resumed = call("/api/partner-operations/" + refused["id"] + "/resume", lea, {"confirmed": True})
    client = await Client.connect(os.environ["TEMPORAL_ADDRESS"])
    assert (await client.get_workflow_handle(resumed["workflow_id"]).result())["status"] == "completed"
    replay = call("/api/partner-operations/" + refused["id"] + "/resume", lea, {"confirmed": True})
    assert replay["status"] == "completed" and replay["effect_count"] == 1
    await start(prepare(refused["order_id"], "bike", "cancel", prefix + "-cancel-resumed"))
    assert call("/api/orders/" + orders[0] + "/partners", lea)["availability"]["bike"] == 2
    report = {"status": "passed", "mode": "fixture-no-llm", "three_concurrent_requests": 3, "resources": 2, "successful_reservations": 2, "refusals": 1, "distinct_resources": True, "refused_request_resumed_after_stock_released": True, "resume_requires_confirmation_and_owner_access": True, "stock_restored_after_cancellation": True}
    Path("/proofs/partner-concurrency-result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


asyncio.run(main())
