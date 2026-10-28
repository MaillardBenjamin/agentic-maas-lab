"""Bounded, session-scoped live metadata. Never stores prompts, results or tokens."""
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
import threading
import time
import os
import secrets
from typing import Literal
import uuid

from fastapi import Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from maas.security import principal

ACTORS = Literal['interface', 'conversation', 'tariffs', 'sav', 'clearing', 'mobility', 'transport', 'bike', 'parking', 'read_catalog', 'search_tariffs', 'read_order', 'read_statement', 'read_provider_context', 'prepare_quote', 'bike_availability', 'bike_apply', 'parking_availability', 'parking_apply']
RUNS = {}
EVENTS = deque(maxlen=4096)
LOCK = threading.RLock()
GENERATION = uuid.uuid4().hex
SEQUENCE = 0
TTL = 900


class ActivityEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    run_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    span_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    protocol: Literal['A2A', 'MCP']
    source: ACTORS
    target: ACTORS
    state: Literal['started', 'completed', 'failed']
    duration_ms: int | None = Field(default=None, ge=0, le=3600000)


def purge():
    now = time.monotonic()
    for key, value in list(RUNS.items()):
        if now - value['_created'] > TTL:
            del RUNS[key]
    while EVENTS and EVENTS[0]['run_id'] not in RUNS:
        EVENTS.popleft()


def visible(run, user):
    return run['_org'] == user['org'] and (run['_owner'] == user['id'] or user['role'] in ('demo', 'supervisor'))


def start(user, title, mode):
    with LOCK:
        purge()
        while len(RUNS) >= 64:
            RUNS.pop(next(iter(RUNS)))
        rid = uuid.uuid4().hex
        RUNS[rid] = {'id': rid, 'title': title, 'mode': mode, 'state': 'running', 'at': datetime.now(timezone.utc).isoformat(), '_owner': user['id'], '_org': user['org'], '_created': time.monotonic()}
        return rid


def append(event, user):
    global SEQUENCE
    with LOCK:
        purge()
        run = RUNS.get(event.run_id)
        # Publisher must act as the exact owner, including privileged demo accounts.
        if not run or (run['_owner'], run['_org']) != (user['id'], user['org']):
            raise HTTPException(404, 'Échange introuvable ou expiré')
        SEQUENCE += 1
        value = event.model_dump()
        EVENTS.append({**value, 'sequence': SEQUENCE, 'at': datetime.now(timezone.utc).isoformat()})


@contextmanager
def exchange(run_id, user, protocol, source, target):
    span_id, began = uuid.uuid4().hex, time.monotonic()
    def emit(state):
        try:
            append(ActivityEvent(run_id=run_id, span_id=span_id, protocol=protocol, source=source, target=target, state=state, duration_ms=None if state == 'started' else min(3600000, round((time.monotonic() - began) * 1000))), user)
        except HTTPException:
            pass  # A bounded observability buffer must not interrupt the request.
    emit('started')
    try:
        yield
    except BaseException:
        emit('failed')
        with LOCK:
            if run_id in RUNS:
                RUNS[run_id]['state'] = 'failed'
        raise
    else:
        emit('completed')
        with LOCK:
            if run_id in RUNS:
                RUNS[run_id]['state'] = 'completed'


def snapshot(user, after=0):
    with LOCK:
        purge()
        allowed = {key for key, run in RUNS.items() if visible(run, user)}
        runs = [{key: value for key, value in run.items() if not key.startswith('_')} for rid, run in RUNS.items() if rid in allowed]
        events = [event for event in EVENTS if event['run_id'] in allowed and event['sequence'] > after]
        return {'generation': GENERATION, 'cursor': SEQUENCE, 'runs': runs[-20:], 'events': events, 'truncated': bool(EVENTS and after and after < EVENTS[0]['sequence'] - 1), 'retention_seconds': TTL}


def publisher(x_activity_token: str = Header(default='')):
    if not secrets.compare_digest(x_activity_token, os.environ.get('ACTIVITY_TOKEN', 'local-activity-only-0123456789')):
        raise HTTPException(403, 'Publication du suivi réservée aux runtimes internes')


def register(app):
    @app.get('/api/agent-activity')
    def feed(after: int = Query(default=0, ge=0), user=Depends(principal)):
        return snapshot(user, after)

    @app.post('/internal/agent-activity', dependencies=[Depends(publisher)])
    def publish(body: ActivityEvent, user=Depends(principal)):
        append(body, user)
        return {'status': 'recorded'}
