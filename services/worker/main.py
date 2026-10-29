import asyncio
import os
from contextlib import suppress
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.worker import Worker
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    import httpx  # Only Activities use this I/O library, never Workflow code.
    from temporalio.contrib.opentelemetry import TracingInterceptor
    from maas.observability import configure, service_headers


@activity.defn
async def set_order_state(payload: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(os.environ.get("API_URL", "http://api:8000") + f"/internal/orders/{payload['order_id']}/state", json={k: v for k, v in payload.items() if k != "order_id"}, headers=service_headers())
        response.raise_for_status()
        return response.json()


@activity.defn
async def issue_card(order_id: str):
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(os.environ.get("CARD_URL", "http://simulator:8001") + "/cards/load", json={"operation_id": order_id, "order_id": order_id}, headers=service_headers())
        response.raise_for_status()
        return response.json()


@workflow.defn(name="PurchaseAndIssue")
class PurchaseAndIssue:
    def __init__(self):
        self.paid = False
        self.resume = False

    @workflow.signal
    def payment_confirmed(self):
        self.paid = True

    @workflow.signal
    def continue_issuance(self):
        self.resume = True

    @workflow.query
    def state(self):
        return {"payment_received": self.paid, "resume_received": self.resume}

    @workflow.run
    async def run(self, args: dict):
        await workflow.wait_condition(lambda: self.paid)
        oid = args["order_id"]
        retry = RetryPolicy(initial_interval=timedelta(seconds=1), maximum_interval=timedelta(seconds=10), maximum_attempts=8)
        async def state(value):
            return await workflow.execute_activity(set_order_state, {"order_id": oid, **value}, start_to_close_timeout=timedelta(seconds=10), retry_policy=retry)
        if args.get("pause"):
            await state({"state": "awaiting_resume"})
            await workflow.wait_condition(lambda: self.resume)
        await state({"state": "issuance_pending"})
        result = await workflow.execute_activity(issue_card, oid, start_to_close_timeout=timedelta(seconds=15), retry_policy=retry)
        await state({"state": "fulfilled", "card": result})
        return result


@activity.defn
async def anchor_proof(batch_id: str):
    async with httpx.AsyncClient(timeout=30) as client:
        result = await client.post(os.environ.get("API_URL", "http://api:8000") + "/internal/proofs/" + batch_id + "/anchor", headers=service_headers())
        result.raise_for_status()
        return result.json()


@workflow.defn(name="ProofAnchoring")
class ProofAnchoring:
    @workflow.run
    async def run(self, batch_id: str):
        return await workflow.execute_activity(anchor_proof, batch_id, start_to_close_timeout=timedelta(seconds=40), retry_policy=RetryPolicy(initial_interval=timedelta(seconds=2), maximum_interval=timedelta(seconds=30), maximum_attempts=30))


@activity.defn
async def delegate_partner(args: dict):
    async with httpx.AsyncClient(timeout=390) as client:
        result = await client.post(os.environ.get("API_URL", "http://api:8000") + "/internal/partner-operations/" + args["operation_id"] + "/dispatch", json={"fixture": args.get("fixture", False)}, headers=service_headers())
        result.raise_for_status()
        return {"operation_id": args["operation_id"], "status": result.json()["status"]}


@activity.defn
async def fail_partner(operation_id: str):
    async with httpx.AsyncClient(timeout=10) as client:
        result = await client.post(os.environ.get("API_URL", "http://api:8000") + "/internal/partner-operations/" + operation_id + "/failed", headers=service_headers())
        result.raise_for_status()


@workflow.defn(name="PartnerInteraction")
class PartnerInteraction:
    @workflow.run
    async def run(self, args: dict):
        try:
            return await workflow.execute_activity(delegate_partner, args, start_to_close_timeout=timedelta(seconds=420), retry_policy=RetryPolicy(initial_interval=timedelta(seconds=5), maximum_interval=timedelta(seconds=30), maximum_attempts=3))
        except Exception:
            await workflow.execute_activity(fail_partner, args["operation_id"], start_to_close_timeout=timedelta(seconds=15))
            raise ApplicationError("Coopération partenaire interrompue ; résultat métier conservé", non_retryable=True)


@activity.defn
async def check_bank(order_id: str):
    async with httpx.AsyncClient(timeout=40) as client:
        result = await client.post(os.environ.get("API_URL", "http://api:8000") + "/internal/orders/" + order_id + "/bridge/status", headers=service_headers())
        result.raise_for_status()
        return result.json()


@workflow.defn(name="BankPaymentWatch")
class BankPaymentWatch:
    @workflow.run
    async def run(self, order_id: str):
        # Bounded demo polling survives browser closure and worker restarts.
        deadline = workflow.now() + timedelta(minutes=15)
        while workflow.now() < deadline:
            try:
                result = await workflow.execute_activity(check_bank, order_id, start_to_close_timeout=timedelta(seconds=45), retry_policy=RetryPolicy(maximum_attempts=2))
                if result.get("settled") or result.get("provider_status") == "RJCT":
                    return result
            except Exception:
                pass  # Next durable timer retries a transient provider/API outage.
            await workflow.sleep(timedelta(seconds=5))
        return {"settled": False, "reason": "watch_window_expired_manual_reconciliation_required"}


async def dispatch_proof_outbox():
    # The durable rows are committed with business transitions. A restart or
    # unavailable chain never loses a pending proof or blocks a purchase.
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            for path in ("/internal/proofs/dispatch", "/internal/abt/billing"):
                try:
                    response = await client.post(os.environ.get("API_URL", "http://api:8000") + path, headers=service_headers())
                    response.raise_for_status()
                except (httpx.HTTPError, ValueError):
                    pass
            await asyncio.sleep(5)


async def main():
    configure("maas-worker")
    for attempt in range(40):
        try:
            client = await Client.connect(os.environ.get("TEMPORAL_ADDRESS", "temporal:7233"), interceptors=[TracingInterceptor()])
            break
        except Exception:
            if attempt == 39:
                raise
            await asyncio.sleep(2)
    # The Worker inherits this dual client/worker interceptor from its Client.
    async with Worker(client, task_queue="maas-ticketing", workflows=[PurchaseAndIssue, ProofAnchoring, PartnerInteraction, BankPaymentWatch], activities=[set_order_state, issue_card, anchor_proof, delegate_partner, fail_partner, check_bank]):
        dispatcher = asyncio.create_task(dispatch_proof_outbox())
        try:
            await asyncio.Event().wait()
        finally:
            dispatcher.cancel()
            with suppress(asyncio.CancelledError):
                await dispatcher


if __name__ == "__main__":
    asyncio.run(main())
