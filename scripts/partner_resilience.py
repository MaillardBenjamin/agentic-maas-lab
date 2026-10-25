"""Queue a real A2A/MCP fixture workflow while the Temporal Worker is stopped."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import uuid
from temporalio.client import Client
from maas.api import log
from maas.db import Session
from maas.partners import PartnerRequest, prepare_operation
from maas.security import USERS
from smoke import call, login, wait

parser = argparse.ArgumentParser()
parser.add_argument("phase", choices=["prepare", "queue-stopped", "check"])
args = parser.parse_args()
path = Path("/proofs/partner-resilience.json")
lea = login("lea")


async def start(op):
    client = await Client.connect(os.environ["TEMPORAL_ADDRESS"])
    return await client.start_workflow("PartnerInteraction", {"operation_id": op["id"], "fixture": True}, id=op["id"], task_queue="maas-ticketing")


if args.phase == "prepare":
    key = "partner-resilience-" + uuid.uuid4().hex
    q = call("/api/quotes", lea, {"products": ["parking"]})
    order = call("/api/orders", lea, {"quote_id": q["id"], "idempotency_key": key})
    call("/api/demo/orders/" + order["id"] + "/pay", lea, {})
    wait(order["id"], "fulfilled", lea)
    with Session.begin() as db:
        op = prepare_operation(db, order["id"], PartnerRequest(partner="parking", action="reserve", confirmed=True, idempotency_key=key), USERS["lea"], log, test_only=True)
    path.write_text(json.dumps({"operation": op, "order_id": order["id"]}))
    print({"status": "prepared", "mode": "fixture-no-llm"})
elif args.phase == "queue-stopped":
    state = json.loads(path.read_text())
    asyncio.run(start(state["operation"]))
    value = call("/api/orders/" + state["order_id"] + "/partners", lea)
    assert not value["bookings"] and value["operations"][0]["status"] == "queued"
    print({"status": "passed", "queued_during_worker_outage": True, "no_effect_before_resume": True})
else:
    state = json.loads(path.read_text())
    async def check():
        client = await Client.connect(os.environ["TEMPORAL_ADDRESS"])
        result = await client.get_workflow_handle(state["operation"]["id"]).result()
        assert result["status"] == "completed", result
        value = call("/api/orders/" + state["order_id"] + "/partners", lea)
        assert len(value["bookings"]) == 1 and value["operations"][0]["effect_count"] == 1
        with Session.begin() as db:
            cancel = prepare_operation(db, state["order_id"], PartnerRequest(partner="parking", action="cancel", confirmed=True, idempotency_key="cancel-" + uuid.uuid4().hex), USERS["lea"], log, test_only=True)
        handle = await start(cancel)
        assert (await handle.result())["status"] == "completed"
    asyncio.run(check())
    report = {"status": "passed", "mode": "fixture-no-llm", "queued_while_worker_stopped": True, "a2a_mcp_resumed": True, "reservation_effect_count": 1, "reservation_cancelled_after_test": True}
    Path("/proofs/partner-resilience-result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
