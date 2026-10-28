"""Gateway authorization, consent, bounded uploads and private routing."""
import hashlib
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from maas import perception
from maas.security import USERS, token


@pytest.fixture
def client():
    app = FastAPI()
    perception.register(app)
    with TestClient(app) as value:
        yield value


def auth(user='lea'):
    return {'Authorization': 'Bearer ' + token(USERS[user])}


def upload_headers():
    return {**auth(), 'X-Capture-Consent': 'true', 'Content-Type': 'video/mp4'}


def test_requires_session(client):
    assert client.get('/api/perception/status').status_code == 401
    assert client.post('/api/perception/jobs', content=b'clip').status_code == 401
    assert client.delete('/api/perception/jobs/' + 'a' * 32).status_code == 401


def test_consent_type_mode_and_limits(client, monkeypatch):
    assert client.post('/api/perception/jobs', headers=auth(), content=b'clip').status_code == 422
    assert client.post('/api/perception/jobs', headers={**upload_headers(), 'Content-Type': 'text/plain'}, content=b'clip').status_code == 415
    assert client.post('/api/perception/jobs?mode=audio', headers=upload_headers(), content=b'clip').status_code == 422
    assert client.post('/api/perception/jobs?language=xx', headers=upload_headers(), content=b'clip').status_code == 422
    assert client.post('/api/perception/jobs', headers=upload_headers(), content=b'').status_code == 422
    monkeypatch.setattr(perception, 'MAX_BYTES', 3)
    assert client.post('/api/perception/jobs', headers=upload_headers(), content=b'clip').status_code == 413


def test_private_routing_and_owner(client, monkeypatch):
    seen = []
    def handle(request):
        seen.append(request)
        return httpx.Response(202, json={'id': 'a' * 32, 'status': 'queued'})
    original = httpx.AsyncClient
    monkeypatch.setattr(perception.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    response = client.post('/api/perception/jobs?mode=vsr&framing=mouth&language=fr', headers=upload_headers(), content=b'clip')
    assert response.status_code == 202
    request = seen[0]
    assert request.url.host == 'perception' and request.url.port == 8005
    assert request.url.params['mode'] == 'vsr' and request.content == b'clip'
    assert request.headers['X-Capture-Consent'] == 'true'
    assert request.headers['X-Perception-Owner'] == hashlib.sha256(b'alize:lea').hexdigest()
    assert 'authorization' not in request.headers
    assert perception.headers(USERS['lea'])['X-Perception-Owner'] != perception.headers(USERS['adult'])['X-Perception-Owner']


def test_unavailable_status_and_owned_job_errors(client, monkeypatch):
    def handle(request):
        if request.url.path == '/health':
            raise httpx.ConnectError('offline', request=request)
        return httpx.Response(404, json={'detail': 'Analyse introuvable ou expirée'})
    original = httpx.AsyncClient
    monkeypatch.setattr(perception.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    response = client.get('/api/perception/status', headers=auth())
    assert response.status_code == 200 and response.json()['ready'] is False
    assert client.get('/api/perception/jobs/' + 'a' * 32, headers=auth()).status_code == 404
    assert client.delete('/api/perception/jobs/' + 'a' * 32, headers=auth()).status_code == 404
    assert client.get('/api/perception/jobs/bad-id', headers=auth()).status_code == 404
