import os
import sqlite3
import json
import httpx
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException

from maas.security import service

app = FastAPI(title="Bouchon avec état · carte et lecteur")
path = os.environ.get("CARD_DB", "/data/card.db")
Path(path).parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(path) as db:
    db.execute("CREATE TABLE IF NOT EXISTS loads (operation TEXT PRIMARY KEY, order_id TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 1)")
    db.execute("CREATE TABLE IF NOT EXISTS faults (id INTEGER PRIMARY KEY, lose_response INTEGER NOT NULL)")
    if "sdk" not in [r[1] for r in db.execute("PRAGMA table_info(loads)")]:
        db.execute("ALTER TABLE loads ADD COLUMN sdk TEXT")


@app.get("/health")
def health():
    return {"status": "ok", "mode": "simulated"}


@app.post("/cards/load", dependencies=[Depends(service)])
def load(payload: dict):
    op = payload.get("operation_id")
    oid = payload.get("order_id")
    if not isinstance(op, str) or not isinstance(oid, str):
        raise HTTPException(422)
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT order_id, attempts, sdk FROM loads WHERE operation=?", (op,)).fetchone()
        if old and old[0] != oid:
            raise HTTPException(409, "Clé déjà liée à un autre chargement")
        if old:
            db.execute("UPDATE loads SET attempts=attempts+1 WHERE operation=?", (op,))
            sdk = json.loads(old[2]) if old[2] else {"mode": "legacy_simulation"}
        else:
            try:
                response = httpx.post(os.environ.get("KEYPLE_URL", "http://keyple:8004") + "/load", json={"operation_id": op}, timeout=10)
                response.raise_for_status()
                sdk = response.json()
            except (httpx.HTTPError, ValueError):
                raise HTTPException(503, "Adaptateur Keyple indisponible ; aucune émission confirmée")
            db.execute("INSERT INTO loads(operation,order_id,sdk) VALUES (?,?,?)", (op, oid, json.dumps(sdk)))
        fault = db.execute("SELECT lose_response FROM faults WHERE id=1").fetchone()
        lose = bool(fault and fault[0] and not old)
        if lose:
            db.execute("UPDATE faults SET lose_response=0 WHERE id=1")
        db.commit()
    if lose:
        raise HTTPException(503, "Écriture effectuée ; réponse perdue simulée")
    return {"operation_id": op, "order_id": oid, "load_count": 1, "mode": "real_sdk_stub_card", "sdk": sdk, "reconciled": bool(old)}


@app.get("/cards", dependencies=[Depends(service)])
def cards():
    with sqlite3.connect(path) as db:
        return [{"operation": r[0], "order_id": r[1], "load_count": 1, "attempts": r[2]} for r in db.execute("SELECT operation,order_id,attempts FROM loads")]


@app.post("/faults/lose-response", dependencies=[Depends(service)])
def fault():
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO faults(id,lose_response) VALUES (1,1) ON CONFLICT(id) DO UPDATE SET lose_response=1")
    return {"armed": True, "mode": "simulated"}
