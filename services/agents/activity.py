"""Best-effort metadata from the actual A2A/MCP call boundaries."""
from contextlib import asynccontextmanager
import contextvars
import os
import time
import uuid

import httpx

context = contextvars.ContextVar('agent_activity', default=None)


@asynccontextmanager
async def exchange(protocol, target):
    scope = context.get()
    began, span = time.monotonic(), uuid.uuid4().hex
    async def emit(state):
        if not scope:
            return
        try:
            async with httpx.AsyncClient(timeout=.7) as client:
                await client.post(os.environ.get('API_URL', 'http://api:8000') + '/internal/agent-activity', headers={'Authorization': 'Bearer ' + scope['token'], 'X-Activity-Token': os.environ.get('ACTIVITY_TOKEN', 'local-activity-only-0123456789')}, json={'run_id': scope['run_id'], 'span_id': span, 'protocol': protocol, 'source': scope['agent'], 'target': target, 'state': state, 'duration_ms': None if state == 'started' else min(3600000, round((time.monotonic() - began) * 1000))})
        except (httpx.HTTPError, ValueError):
            pass  # Observability must never authorize or interrupt a business effect.
    await emit('started')
    try:
        yield
    except BaseException:
        await emit('failed')
        raise
    else:
        await emit('completed')


def trace_headers():
    scope = context.get()
    return {'X-MaaS-Activity-ID': scope['run_id']} if scope else {}
