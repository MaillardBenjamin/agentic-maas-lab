from concurrent.futures import ThreadPoolExecutor
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import pytest
from maas.domain import canonical
from maas.proofs import sign_manifest


def test_concurrent_first_signatures_publish_one_complete_private_key(tmp_path, monkeypatch):
    path = tmp_path / "key"
    monkeypatch.setenv("PROOF_KEY_PATH", str(path))
    manifest = {"schema_version": 1, "events": [{"type": "test", "digest": "abc"}]}
    with ThreadPoolExecutor(16) as pool:
        results = list(pool.map(lambda _: sign_manifest(manifest), range(40)))
    assert len({r["public_key"] for r in results}) == 1
    assert len({r["signature"] for r in results}) == 1
    assert len(path.read_bytes()) == 32
    assert path.stat().st_mode & 0o777 == 0o600
    result = results[0]
    public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(result["public_key"]))
    public.verify(bytes.fromhex(result["signature"]), canonical(manifest))
    with pytest.raises(InvalidSignature):
        public.verify(bytes.fromhex(result["signature"]), canonical({"schema_version": 2, "events": []}))
