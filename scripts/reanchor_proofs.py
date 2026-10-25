"""Explicit local operator recovery. Preserve prior chain references, verify off-chain signatures."""
import asyncio
import json
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from maas.db import Session, Record
from maas.domain import canonical, digest


async def main():
    deployment = json.loads(Path("/proofs/deployment.json").read_text())
    client = await Client.connect(os.environ.get("TEMPORAL_ADDRESS", "temporal:7233"))
    with Session() as db:
        records = [r.data for r in db.scalars(select(Record).where(Record.kind == "proof")) if r.data["status"] == "chain_reset"]
    for proof in records:
        assert digest(proof["manifest"]) == proof["digest"]
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(proof["public_key"])).verify(bytes.fromhex(proof["signature"]), canonical(proof["manifest"]))
        # Workflow id changes for the new local chain instance, business batch id does not.
        wid = proof["id"] + "-" + deployment["instance_id"]
        try:
            await client.start_workflow("ProofAnchoring", proof["id"], id=wid, task_queue="maas-ticketing", id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
        except WorkflowAlreadyStartedError:
            pass
        print({"batch": proof["id"], "recovery_requested": True, "previous_references_preserved": True})

asyncio.run(main())
