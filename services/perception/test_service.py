"""Service boundary tests; no mocked output is claimed as model inference."""
import threading
import time
import pytest
from fastapi.testclient import TestClient
import app as engine
from media import MediaError, inspect_media, normalize_video, mouth_frames


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('SERVICE_TOKEN', 'unit-test-internal-token')
    monkeypatch.setattr(engine, 'VERIFIED', True)
    engine.JOBS.clear()
    # Skip expensive startup hash: real hashes are tested separately by the smoke.
    with TestClient(engine.app) as value:
        yield value
    for job in engine.JOBS.values():
        job['cancel'].set()
    engine.JOBS.clear()


def headers(who='a'):
    return {'X-Service-Token': 'unit-test-internal-token', 'X-Perception-Owner': who * 64, 'X-Capture-Consent': 'true', 'Content-Type': 'video/mp4'}


def test_private_auth_and_invalid_uploads(client, monkeypatch):
    assert client.get('/jobs/a').status_code == 403
    assert client.get('/jobs/a', headers={**headers(), 'X-Perception-Owner': 'invalid'}).status_code == 403
    assert client.post('/jobs', content=b'clip', headers={**headers(), 'X-Capture-Consent': ''}).status_code == 422
    assert client.post('/jobs', content=b'', headers=headers()).status_code == 422
    assert client.post('/jobs', content=b'clip', headers={**headers(), 'Content-Type': 'text/plain'}).status_code == 415
    monkeypatch.setattr(engine, 'MAX_BYTES', 3)
    assert client.post('/jobs', content=b'clip', headers=headers()).status_code == 413


def test_owner_isolation_deletion_and_expiration(client):
    cancel = threading.Event()
    engine.JOBS['one'] = {'id': 'one', 'owner': 'a' * 64, 'cancel': cancel, 'created': time.monotonic(), 'status': 'completed', 'result': {'text': 'private'}, 'error': None}
    assert client.get('/jobs/one', headers=headers('b')).status_code == 404
    assert client.delete('/jobs/one', headers=headers('b')).status_code == 404
    assert client.get('/jobs/one', headers=headers()).json()['result']['text'] == 'private'
    assert client.delete('/jobs/one', headers=headers()).status_code == 200 and cancel.is_set()
    assert client.get('/jobs/one', headers=headers()).status_code == 404
    engine.JOBS['expired'] = {'created': time.monotonic() - engine.TTL - 1, 'cancel': threading.Event()}
    engine.purge()
    assert 'expired' not in engine.JOBS
    engine.JOBS['idle'] = {'cancel': threading.Event()}
    engine.expire('idle')
    assert 'idle' not in engine.JOBS


def test_busy_and_unverified_are_explicit(client, monkeypatch):
    assert engine.SLOT.acquire(blocking=False)
    try:
        assert client.post('/jobs', headers=headers(), content=b'clip').status_code == 429
    finally:
        engine.SLOT.release()
    monkeypatch.setattr(engine, 'VERIFIED', False)
    assert client.post('/jobs', headers=headers(), content=b'clip').status_code == 503


def test_invalid_media_and_automatic_face_rejection(tmp_path):
    import subprocess
    invalid = tmp_path / 'bad.mp4'
    invalid.write_bytes(b'this is not a video')
    with pytest.raises(MediaError):
        inspect_media(invalid)
    source = tmp_path / 'blank.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=black:s=320x240:r=25:d=0.8', '-threads', '1', '-y', str(source)], check=True)
    assert inspect_media(source)['has_audio'] is False
    normalized = tmp_path / 'normalized.mp4'
    normalize_video(source, normalized)
    with pytest.raises(MediaError, match='Visage insuffisamment visible'):
        mouth_frames(normalized, engine.MODEL_DIR, 'face')


def test_cancel_terminates_worker_and_deletes_media(tmp_path, monkeypatch):
    class Process:
        stopped = False
        def poll(self):
            return 0 if self.stopped else None
        def terminate(self):
            self.stopped = True
        def wait(self, **kwargs):
            return 0
    process = Process()
    monkeypatch.setattr(engine.subprocess, 'Popen', lambda *args, **kwargs: process)
    directory = tmp_path / 'private-job'
    directory.mkdir()
    (directory / 'input.video').write_bytes(b'unit-test-media')
    job = {'cancel': threading.Event()}
    job['cancel'].set()
    assert engine.SLOT.acquire(blocking=False)
    engine.execute(job, str(directory), 'vsr', 'mouth', 'fr')
    assert process.stopped and not directory.exists()
    assert job['status'] == 'failed'
    assert engine.SLOT.acquire(blocking=False)
    engine.SLOT.release()
