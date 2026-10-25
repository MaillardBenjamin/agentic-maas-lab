import json
import uuid
from pathlib import Path
from web3 import Web3

web3 = Web3(Web3.HTTPProvider("http://anvil:8545"))
assert web3.eth.chain_id == 31337, "Déploiement réservé au réseau local 31337"
path = Path("/proofs/deployment.json")
reset = False
if path.exists():
    existing = json.loads(path.read_text())
    if existing["chain_id"] == 31337 and web3.eth.get_code(existing["address"]):
        print(json.dumps({"status": "existing", "address": existing["address"], "chain_id": 31337}))
        raise SystemExit(0)
    reset = True
artifact = json.loads(Path("/contracts/out/ProofRegistry.sol/ProofRegistry.json").read_text())
account = web3.eth.accounts[0]  # Development account unlocked by local Anvil only.
contract = web3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"]["object"])
tx = contract.constructor().transact({"from": account})
receipt = web3.eth.wait_for_transaction_receipt(tx)
assert receipt.status == 1
manifest = {"chain_id": 31337, "instance_id": uuid.uuid4().hex, "address": receipt.contractAddress, "publisher": account, "transaction": tx.hex(), "abi": artifact["abi"]}
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(manifest, indent=2))
if reset:
    from maas.db import Session, Record
    from sqlalchemy import select
    with Session.begin() as db:
        for proof in db.scalars(select(Record).where(Record.kind == "proof")):
            if (proof.data.get("chain") or {}).get("instance_id") == manifest["instance_id"]:
                continue
            previous = proof.data.get("previous_chains", [])
            if proof.data.get("chain"):
                previous = previous + [proof.data["chain"]]
            proof.data = {**proof.data, "status": "chain_reset", "previous_chains": previous, "chain": None}
print(json.dumps({k: v for k,v in manifest.items() if k != "abi"}))
