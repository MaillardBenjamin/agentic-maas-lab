"""Authenticated gateway: media never enters the database, graph, agents or traces."""
import hashlib
import os
import re
from typing import Literal

import httpx
from fastapi import Depends, Header, HTTPException, Request
from maas.security import principal

MAX_BYTES = 20 * 1024 * 1024


def headers(user):
    identity = hashlib.sha256((user['org'] + ':' + user['id']).encode()).hexdigest()
    return {'X-Service-Token': os.environ.get('SERVICE_TOKEN', 'local-services-only-0123456789'), 'X-Perception-Owner': identity}


async def upstream(path, user, method='GET', **kwargs):
    # Fixed private destination; never constructed from a user URL or media metadata.
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(method, 'http://perception:8005' + path, headers={**headers(user), **kwargs.pop('headers', {})}, **kwargs)
        data = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, 'Le moteur vidéo local est indisponible. Vous pouvez continuer par écrit.') from None
    if response.is_error:
        raise HTTPException(response.status_code, data.get('detail', 'Analyse vidéo indisponible.'))
    return data


def register(app):
    @app.get('/api/perception/status')
    async def status(user=Depends(principal)):
        try:
            return await upstream('/health', user)
        except HTTPException:
            return {'status': 'unavailable', 'ready': False, 'reason': 'Le moteur vidéo local n’est pas démarré.', 'engine': 'mwhisper-flamingo-small', 'streaming': False}

    @app.post('/api/perception/jobs', status_code=202)
    async def create(request: Request, mode: Literal['avsr', 'vsr'] = 'avsr', framing: Literal['face', 'mouth'] = 'face', language: Literal['fr', 'en', 'es', 'de', 'it', 'pt', 'el', 'ru', 'ar'] = 'fr', user=Depends(principal), x_capture_consent: str = Header(default='')):
        if x_capture_consent != 'true':
            raise HTTPException(422, 'Confirmez l’envoi de cette séquence au moteur local.')
        content_type = request.headers.get('content-type', '').split(';')[0]
        if content_type not in {'video/mp4', 'video/webm', 'video/quicktime', 'application/octet-stream'}:
            raise HTTPException(415, 'Utilisez une vidéo MP4 ou WebM.')
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_BYTES:
                raise HTTPException(413, 'Vidéo trop volumineuse : 20 Mo maximum.')
            chunks.append(chunk)
        if not size:
            raise HTTPException(422, 'La vidéo est vide.')
        return await upstream('/jobs', user, 'POST', params={'mode': mode, 'framing': framing, 'language': language}, content=b''.join(chunks), headers={'Content-Type': content_type, 'X-Capture-Consent': 'true'})

    @app.get('/api/perception/jobs/{job_id}')
    async def job(job_id: str, user=Depends(principal)):
        if not re.fullmatch('[a-f0-9]{32}', job_id):
            raise HTTPException(404, 'Analyse introuvable')
        return await upstream('/jobs/' + job_id, user)

    @app.delete('/api/perception/jobs/{job_id}')
    async def remove(job_id: str, user=Depends(principal)):
        if not re.fullmatch('[a-f0-9]{32}', job_id):
            raise HTTPException(404, 'Analyse introuvable')
        return await upstream('/jobs/' + job_id, user, 'DELETE')
