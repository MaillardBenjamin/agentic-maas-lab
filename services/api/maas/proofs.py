import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from web3 import Web3

from maas.domain import canonical, digest


def sign_manifest(manifest):
    path = Path(os.environ.get("PROOF_KEY_PATH", "/proofs/signing.key"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        key = Ed25519PrivateKey.generate()
        temporary = path.with_name(".key-" + uuid.uuid4().hex)
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))
                f.flush()
                os.fsync(f.fileno())
            # Publish only a complete key. Concurrent first requests use the same winner.
            os.link(temporary, path)
        except FileExistsError:
            pass
        finally:
            temporary.unlink(missing_ok=True)
    key = Ed25519PrivateKey.from_private_bytes(path.read_bytes())
    return {"signature": key.sign(canonical(manifest)).hex(), "public_key": key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()}


def anchor_batch(batch_id, batch_digest, schema_version=1):
    manifest = json.loads(Path("/proofs/deployment.json").read_text())
    w3 = Web3(Web3.HTTPProvider(os.environ.get("ANVIL_URL", "http://anvil:8545"), request_kwargs={"timeout": 8}))
    if w3.eth.chain_id != 31337 or manifest["chain_id"] != 31337:
        raise ValueError("Réseau non local refusé")
    if not w3.eth.get_code(manifest["address"]):
        raise ValueError("Contrat absent après réinitialisation du réseau")
    contract = w3.eth.contract(address=manifest["address"], abi=manifest["abi"])
    key = bytes.fromhex(digest({"batch_id": batch_id}))
    expected = bytes.fromhex(batch_digest)
    previous = contract.functions.proofs(key).call()
    txhash = None
    if previous[2]:
        if previous[0] != expected or previous[1] != schema_version:
            raise ValueError("Conflit sur la preuve existante")
        block = previous[2]
    else:
        tx = contract.functions.anchor(key, expected, schema_version).transact({"from": manifest["publisher"]})
        receipt = w3.eth.wait_for_transaction_receipt(tx, timeout=15)
        if receipt.status != 1:
            raise ValueError("Échec de transaction")
        txhash, block = tx.hex(), receipt.blockNumber
    return {"chain_id": 31337, "instance_id": manifest.get("instance_id", "legacy"), "contract": manifest["address"], "transaction": txhash, "block": block, "anchored_at": datetime.fromtimestamp(w3.eth.get_block(block)["timestamp"], timezone.utc).isoformat(), "verified": True, "mode": "local_blockchain", "digest": batch_digest}


def with_anchor_time(proof):
    """Read existing block time only for the matching local deployment."""
    chain = proof.get("chain", {})
    if not chain or chain.get("anchored_at"):
        return proof
    try:
        deployment = json.loads(Path("/proofs/deployment.json").read_text())
        if chain.get("instance_id") != deployment.get("instance_id"):
            return proof
        w3 = Web3(Web3.HTTPProvider(os.environ.get("ANVIL_URL", "http://anvil:8545"), request_kwargs={"timeout": 3}))
        if w3.eth.chain_id != chain["chain_id"]:
            return proof
        timestamp = w3.eth.get_block(chain["block"])["timestamp"]
        return {**proof, "chain": {**chain, "anchored_at": datetime.fromtimestamp(timestamp, timezone.utc).isoformat()}}
    except Exception:
        return proof


def verify_record(proof):
    """Fresh, read-only signature and contract checks. Never trusts cached verified=true."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    base = {"id": proof["id"], "stage": proof.get("stage", "usage_batch"), "origin": proof.get("origin", "business_transition"), "recorded_at": proof.get("recorded_at"), "checked_at": datetime.now(timezone.utc).isoformat()}
    try:
        if digest(proof["manifest"]) != proof["digest"]:
            return {**base, "status": "invalid"}
        if not proof.get("signature"):
            return {**base, "status": "invalid" if proof["status"] == "anchored" else "failed" if proof["status"] == "failed" else "pending"}
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(proof["public_key"])).verify(bytes.fromhex(proof["signature"]), canonical(proof["manifest"]))
    except Exception:
        return {**base, "status": "invalid"}
    try:
        deployment = json.loads(Path("/proofs/deployment.json").read_text())
        chain = proof.get("chain", {})
        if chain and (chain.get("instance_id"), chain.get("contract")) != (deployment.get("instance_id"), deployment["address"]):
            return {**base, "status": "deployment_changed"}
        w3 = Web3(Web3.HTTPProvider(os.environ.get("ANVIL_URL", "http://anvil:8545"), request_kwargs={"timeout": 3}))
        if w3.eth.chain_id != 31337 or not w3.eth.get_code(deployment["address"]):
            return {**base, "status": "chain_unavailable"}
        contract = w3.eth.contract(address=deployment["address"], abi=deployment["abi"])
        found = contract.functions.proofs(bytes.fromhex(digest({"batch_id": proof["id"]}))).call()
        if not found[2]:
            return {**base, "status": "not_anchored"}
        if found[0] != bytes.fromhex(proof["digest"]) or found[1] != proof["manifest"]["schema_version"]:
            return {**base, "status": "invalid"}
        return {**base, "status": "verified", "chain_id": 31337, "contract": deployment["address"], "block": found[2], "digest": proof["digest"], "scope": "integrity_of_recorded_content"}
    except Exception:
        return {**base, "status": "chain_unavailable"}
