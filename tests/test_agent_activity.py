"""Activity is observed metadata, bounded and bound to authenticated ownership."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from maas import agent_activity as activity
from maas.security import USERS, token


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('ACTIVITY_TOKEN', 'activity-test-secret')
    activity.RUNS.clear()
    activity.EVENTS.clear()
    app = FastAPI()
    activity.register(app)
    with TestClient(app) as value:
        yield value
    activity.RUNS.clear()
    activity.EVENTS.clear()


def auth(identity='lea', internal=False):
    return {'Authorization': 'Bearer ' + token(USERS[identity]), **({'X-Activity-Token': 'activity-test-secret'} if internal else {})}


def event(rid, **kw):
    return {'run_id': rid, 'span_id': 'a' * 32, 'protocol': 'MCP', 'source': 'tariffs', 'target': 'read_catalog', 'state': 'started', **kw}


def test_authentication_and_unforgeable_public_events(client):
    rid = activity.start(USERS['lea'], 'Dialogue', 'ollama_local')
    assert client.get('/api/agent-activity').status_code == 401
    assert client.post('/internal/agent-activity', headers=auth(), json=event(rid)).status_code == 403
    assert client.post('/internal/agent-activity', headers={'X-Activity-Token': 'activity-test-secret'}, json=event(rid)).status_code == 401
    assert client.post('/internal/agent-activity', headers=auth('adult', True), json=event(rid)).status_code == 404
    assert client.post('/internal/agent-activity', headers=auth(internal=True), json=event(rid, prompt='private')).status_code == 422
    assert client.post('/internal/agent-activity', headers=auth(internal=True), json=event(rid, target='invented-agent')).status_code == 422


def test_incremental_started_completed_and_user_isolation(client):
    rid = activity.start(USERS['lea'], 'Dialogue', 'ollama_local')
    response = client.post('/internal/agent-activity', headers=auth(internal=True), json=event(rid))
    assert response.status_code == 200
    first = client.get('/api/agent-activity', headers=auth()).json()
    assert len(first['events']) == 1 and first['events'][0]['state'] == 'started'
    assert len(first['runs']) == 1 and '_owner' not in str(first)
    assert 'token' not in str(first) and 'Authorization' not in str(first)
    assert client.get('/api/agent-activity', headers=auth('adult')).json()['runs'] == []
    supervisor = client.get('/api/agent-activity', headers=auth('supervisor')).json()
    assert len(supervisor['events']) == 1
    client.post('/internal/agent-activity', headers=auth(internal=True), json=event(rid, state='completed', duration_ms=42))
    after = client.get('/api/agent-activity?after=' + str(first['cursor']), headers=auth()).json()
    assert len(after['events']) == 1 and after['events'][0]['duration_ms'] == 42
    assert after['cursor'] > first['cursor']


def test_foreign_organization_expiration_and_buffer_bounds(client, monkeypatch):
    other = {**USERS['lea'], 'org': 'different'}
    activity.start(other, 'Other org', 'ollama_local')
    assert not client.get('/api/agent-activity', headers=auth('supervisor')).json()['runs']
    rid = activity.start(USERS['lea'], 'Dialogue', 'ollama_local')
    activity.RUNS[rid]['_created'] -= activity.TTL + 1
    assert client.post('/internal/agent-activity', headers=auth(internal=True), json=event(rid)).status_code == 404
    for _ in range(70):
        activity.start(USERS['lea'], 'Dialogue', 'ollama_local')
    assert len(activity.RUNS) <= 64
    assert len(client.get('/api/agent-activity', headers=auth()).json()['runs']) <= 20


def test_root_failure_and_eviction_do_not_change_business_result(client):
    rid = activity.start(USERS['lea'], 'Dialogue', 'ollama_local')
    with pytest.raises(RuntimeError):
        with activity.exchange(rid, USERS['lea'], 'A2A', 'interface', 'conversation'):
            assert activity.snapshot(USERS['lea'])['events'][-1]['state'] == 'started'
            raise RuntimeError('upstream failed')
    assert activity.RUNS[rid]['state'] == 'failed'
    assert activity.snapshot(USERS['lea'])['events'][-1]['state'] == 'failed'
    with activity.exchange(rid, USERS['lea'], 'A2A', 'interface', 'conversation'):
        activity.RUNS.pop(rid)
    # An evicted feed never turns a successful business response into a 404.
