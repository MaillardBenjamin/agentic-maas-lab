"""Private AVSR service: owned ephemeral jobs, one bounded inference at a time."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from media import MAX_BYTES, MAX_SECONDS

MODEL_DIR = Path(os.environ.get('MODEL_DIR', '/models'))
JOBS = {}
MUTEX = threading.Lock()
SLOT = threading.BoundedSemaphore(1)
POOL = ThreadPoolExecutor(max_workers=1)
VERIFIED = False
ASSET_ERROR = 'Modèles non vérifiés.'
TTL = 900


def verify_assets():
    global VERIFIED, ASSET_ERROR
    try:
        manifest = json.loads(Path('/app/assets.json').read_text())
        for asset in manifest['assets']:
            path = MODEL_DIR / asset['name']
            if not path.is_file() or path.stat().st_size != asset['bytes']:
                raise ValueError('missing_asset')
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            if digest.hexdigest() != asset['sha256']:
                raise ValueError('invalid_digest')
        VERIFIED, ASSET_ERROR = True, ''
    except (OSError, ValueError, KeyError):
        VERIFIED, ASSET_ERROR = False, 'Poids ou ressources visuelles absents ou invalides. Exécutez make perception-assets.'


@asynccontextmanager
async def lifespan(_app):
    await asyncio.to_thread(verify_assets)
    yield


app = FastAPI(title='Alizé · perception audiovisuelle locale', lifespan=lifespan)


def owner(x_service_token: str = Header(default=''), x_perception_owner: str = Header(default='')):
    expected = os.environ.get('SERVICE_TOKEN', '')
    if not expected or not secrets.compare_digest(expected, x_service_token):
        raise HTTPException(403, 'Service non autorisé')
    if len(x_perception_owner) != 64 or any(c not in '0123456789abcdef' for c in x_perception_owner):
        raise HTTPException(403, 'Session de perception requise')
    return x_perception_owner


def purge():
    now = time.monotonic()
    for key in list(JOBS):
        job = JOBS[key]
        if now - job['created'] > TTL:
            job['cancel'].set()
            if job.get('expiry'):
                job['expiry'].cancel()
            del JOBS[key]


def expire(job_id):
    # Expire even when nobody polls the API again.
    with MUTEX:
        job = JOBS.pop(job_id, None)
        if job:
            job['cancel'].set()


def owned(job_id, who):
    with MUTEX:
        purge()
        job = JOBS.get(job_id)
        if not job or job['owner'] != who:
            raise HTTPException(404, 'Analyse introuvable ou expirée')
        return job


def public(job):
    return {key: job[key] for key in ['id', 'status', 'result', 'error']}


@app.get('/health')
def health():
    return {'status': 'ok', 'ready': VERIFIED, 'engine': 'mwhisper-flamingo-small', 'mode': 'real_model', 'reason': ASSET_ERROR, 'languages': ['fr', 'en', 'es', 'de', 'it', 'pt', 'el', 'ru', 'ar'], 'modalities': ['avsr', 'vsr'], 'max_bytes': MAX_BYTES, 'max_seconds': MAX_SECONDS, 'device': 'cpu', 'streaming': False, 'retention_seconds': TTL}


def execute(job, directory, mode, framing, language):
    path = Path(directory)
    process = None
    try:
        job['status'] = 'processing'
        process = subprocess.Popen([sys.executable, '/app/infer.py', '--input', str(path / 'input.video'), '--output', str(path / 'result.json'), '--mode', mode, '--framing', framing, '--language', language], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={**os.environ, 'OMP_NUM_THREADS': '3', 'OPENBLAS_NUM_THREADS': '3'})
        deadline = time.monotonic() + 300
        while process.poll() is None:
            if job['cancel'].wait(.25) or time.monotonic() >= deadline:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise TimeoutError()
        if job['cancel'].is_set():
            return
        if process.returncode != 0 or not (path / 'result.json').exists():
            raise RuntimeError('inference_process_failed')
        value = json.loads((path / 'result.json').read_text())
        with MUTEX:
            if value['ok']:
                job['result'] = value['result']
                job['status'] = 'completed'
            else:
                job['status'] = 'failed'
                job['error'] = value['error']
                job['diagnostic'] = value.get('diagnostic')
    except TimeoutError:
        job['status'], job['error'] = 'failed', 'Analyse interrompue ou trop longue. Essayez une séquence plus courte.'
    except Exception:
        job['status'], job['error'] = 'failed', 'L’analyse vidéo n’a pas abouti. Aucun texte n’a été envoyé aux agents.'
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        shutil.rmtree(directory, ignore_errors=True)
        SLOT.release()


@app.post('/jobs', status_code=202)
async def submit(request: Request, mode: Literal['avsr', 'vsr'] = 'avsr', framing: Literal['face', 'mouth'] = 'face', language: Literal['fr', 'en', 'es', 'de', 'it', 'pt', 'el', 'ru', 'ar'] = 'fr', who=Depends(owner), x_capture_consent: str = Header(default='')):
    if x_capture_consent != 'true':
        raise HTTPException(422, 'Confirmez l’envoi de cette séquence pour la transcription locale.')
    if not VERIFIED:
        raise HTTPException(503, ASSET_ERROR)
    if request.headers.get('content-type', '').split(';')[0] not in {'video/mp4', 'video/webm', 'video/quicktime', 'application/octet-stream'}:
        raise HTTPException(415, 'Utilisez une vidéo MP4 ou WebM.')
    if not SLOT.acquire(blocking=False):
        raise HTTPException(429, 'Une analyse est déjà en cours. Réessayez dans quelques instants.')
    directory = tempfile.mkdtemp(prefix='maas-perception-')
    try:
        size = 0
        with (Path(directory) / 'input.video').open('wb') as stream:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, 'Vidéo trop volumineuse : 20 Mo maximum.')
                stream.write(chunk)
        if not size:
            raise HTTPException(422, 'La vidéo est vide.')
        job = {'id': uuid.uuid4().hex, 'owner': who, 'created': time.monotonic(), 'cancel': threading.Event(), 'status': 'queued', 'result': None, 'error': None}
        with MUTEX:
            purge()
            if len(JOBS) >= 12:
                raise HTTPException(429, 'Trop d’analyses récentes. Attendez leur expiration.')
            JOBS[job['id']] = job
            job['expiry'] = threading.Timer(TTL, expire, args=(job['id'],))
            job['expiry'].daemon = True
            job['expiry'].start()
        POOL.submit(execute, job, directory, mode, framing, language)
        return public(job)
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        SLOT.release()
        raise


@app.get('/jobs/{job_id}')
def status(job_id: str, who=Depends(owner)):
    return public(owned(job_id, who))


@app.delete('/jobs/{job_id}')
def cancel(job_id: str, who=Depends(owner)):
    job = owned(job_id, who)
    job['cancel'].set()
    with MUTEX:
        JOBS.pop(job_id, None)
        if job.get('expiry'):
            job['expiry'].cancel()
    return {'status': 'deleted'}
