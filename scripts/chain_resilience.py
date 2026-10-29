import json
import sys
import time
from pathlib import Path
from web3 import Web3
from maas.proofs import anchor_batch
from smoke import call, login

path = Path("/proofs/chain-resilience.json")
web3 = Web3(Web3.HTTPProvider("http://anvil:8545"))
if sys.argv[1] == "prepare":
    auth = login("demo")
    for _ in range(40):
        proofs = call("/api/proofs", auth)
        if proofs and all(p["status"] == "anchored" for p in proofs):
            break
        time.sleep(.5)
    assert proofs and all(p["status"] == "anchored" for p in proofs), "Ancrage en cours ou en échec après attente bornée"
    path.write_text(json.dumps({"block": web3.eth.block_number, "proofs": proofs}))
    print({"phase": "prepare", "block": web3.eth.block_number, "proofs": len(proofs)})
else:
    state = json.loads(path.read_text())
    assert web3.eth.block_number >= state["block"], "Local chain lost block environment"
    for proof in state["proofs"]:
        verified = anchor_batch(proof["id"], proof["digest"], proof["manifest"]["schema_version"])
        assert verified["transaction"] is None, "Proof missing after restart: unexpected new transaction"
        assert verified["block"] == proof["chain"]["block"]
    print({"status": "passed", "anvil_restart": True, "persisted_registry_proofs": len(state["proofs"]), "no_new_transactions": True})
