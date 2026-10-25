import json
import time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from maas.domain import canonical, digest
from maas.proofs import anchor_batch
from smoke import call, login

demo = login("demo")
orders = call("/api/orders", demo)
oid = next(o["id"] for o in orders if len(call("/api/orders/" + o["id"], demo)["events"]) > 0)
proof = call("/api/proofs/" + oid, demo, {})
for _ in range(40):
    value = next(p for p in call("/api/proofs", demo) if p["id"] == proof["id"])
    if value["status"] == "anchored":
        break
    time.sleep(1)
assert value["status"] == "anchored", value
pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(value["public_key"]))
pub.verify(bytes.fromhex(value["signature"]), canonical(value["manifest"]))
assert digest(value["manifest"]) == value["digest"]
assert value["chain"]["chain_id"] == 31337 and value["chain"]["verified"]
assert call("/api/proofs/" + oid, demo, {})["id"] == value["id"]
# A real second contract read performs no second transaction.
again = anchor_batch(value["id"], value["digest"])
assert again["block"] == value["chain"]["block"] and again["transaction"] is None
try:
    pub.verify(bytes.fromhex(value["signature"]), canonical({"schema_version": 1, "events": []}))
    raise AssertionError("Tampered manifest accepted")
except InvalidSignature:
    pass
print(json.dumps({"status": "passed", "chain": value["chain"], "checks": ["Temporal anchoring", "Ed25519 verification", "on-chain read", "idempotence", "tamper rejected"]}, indent=2))
