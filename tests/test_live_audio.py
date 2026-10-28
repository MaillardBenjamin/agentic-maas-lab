import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from maas import live_audio
from maas.security import USERS, token


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv('AI_ENABLED', 'true')
    monkeypatch.setenv('AGENT_MODE', 'ollama')
    monkeypatch.setenv('OPENAI_LIVE_AUDIO_ENABLED', 'true')
    monkeypatch.setenv('OPENAI_API_KEY', 'unit-test-primary-secret-never-exposed')
    monkeypatch.setenv('OPENAI_REALTIME_MODEL', 'gpt-realtime-2.1-mini')
    reservations = []
    monkeypatch.setattr(live_audio, 'reserve', reservations.append)
    app = FastAPI()
    live_audio.register(app)
    with TestClient(app) as client:
        yield client, reservations


def auth():
    return {'Authorization': 'Bearer ' + token(USERS['lea'])}


def test_audio_needs_session_and_explicit_consent(setup):
    client, reservations = setup
    assert client.get('/api/voice/status').status_code == 401
    assert client.post('/api/voice/session', json={'consent': True}).status_code == 401
    for payload in [{}, {'consent': False}, {'consent': True, 'images': True}, {'consent': True, 'model': 'other'}]:
        assert client.post('/api/voice/session', headers=auth(), json=payload).status_code == 422
    assert reservations == []


def test_cloud_audio_is_separate_from_local_agents_and_respects_global_disable(setup, monkeypatch):
    client, reservations = setup
    assert client.get('/api/voice/status', headers=auth()).json()['configured'] is True
    monkeypatch.setenv('AI_ENABLED', 'false')
    assert client.get('/api/voice/status', headers=auth()).json()['configured'] is False
    assert client.post('/api/voice/session', headers=auth(), json={'consent': True}).status_code == 503
    assert reservations == []


def test_configuration_disallows_missing_key_wrong_model_or_disabled_audio(setup, monkeypatch):
    client, _ = setup
    for variable, value in [('OPENAI_API_KEY', ''), ('OPENAI_REALTIME_MODEL', 'arbitrary-model'), ('OPENAI_LIVE_AUDIO_ENABLED', 'false')]:
        with monkeypatch.context() as current:
            current.setenv(variable, value)
            assert client.get('/api/voice/status', headers=auth()).json()['configured'] is False


def test_only_short_lived_secret_is_returned_and_no_video_is_configured(setup, monkeypatch):
    import json
    client, reservations = setup
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={'value': 'ek_unit-test-ephemeral', 'expires_at': 1000, 'session': {'sensitive': 'not-returned'}})
    original = httpx.AsyncClient
    monkeypatch.setattr(live_audio.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    result = client.post('/api/voice/session', headers=auth(), json={'consent': True})
    assert result.status_code == 200
    value = result.json()
    assert value['value'] == 'ek_unit-test-ephemeral'
    assert value['audio_only'] and value['video_sent_to_openai'] is False
    assert 'unit-test-primary-secret' not in result.text and 'sensitive' not in result.text
    request = requests[0]
    assert str(request.url) == 'https://api.openai.com/v1/realtime/client_secrets'
    assert len(request.headers['OpenAI-Safety-Identifier']) == 64
    payload = json.loads(request.content)
    assert payload['expires_after']['seconds'] == 30
    assert payload['session']['output_modalities'] == ['audio']
    assert 'image' not in payload['session'] and 'video' not in payload['session']
    assert [tool['name'] for tool in payload['session']['tools']] == ['ask_ticketing_agent']
    assert reservations == [300]


def test_provider_failure_does_not_expose_credentials_or_silently_change_mode(setup, monkeypatch):
    client, _ = setup
    def handle(request):
        return httpx.Response(401, json={'error': 'unit-test-primary-secret-never-exposed'})
    original = httpx.AsyncClient
    monkeypatch.setattr(live_audio.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    result = client.post('/api/voice/session', headers=auth(), json={'consent': True})
    assert result.status_code == 502 and 'unit-test-primary-secret' not in result.text
