"""Real OpenAI audio-only test using an official public sample, never a webcam."""
import argparse
import asyncio
import audioop
import base64
import json
from pathlib import Path
import wave

import httpx
from websockets.asyncio.client import connect


async def run(sample, output):
    async with httpx.AsyncClient(base_url='http://api:8000', timeout=30) as client:
        auth = {'Authorization': 'Bearer ' + (await client.post('/api/demo/login/lea')).json()['access_token']}
        config = (await client.get('/api/voice/status', headers=auth)).json()
        assert config['configured'] and config['audio_only'] and not config['video_sent_to_openai']
        response = await client.post('/api/voice/session', headers=auth, json={'consent': True})
        response.raise_for_status()
        session = response.json()
    with wave.open(str(sample)) as source:
        assert source.getsampwidth() == 2
        channels, rate, frames = source.getnchannels(), source.getframerate(), source.readframes(source.getnframes())
    if channels == 2:
        frames = audioop.tomono(frames, 2, .5, .5)
    else:
        assert channels == 1
    pcm = audioop.ratecv(frames, 2, 1, rate, 24000, None)[0]
    gain = min(4, 28000 / max(1, audioop.max(pcm, 2)))
    pcm = audioop.mul(pcm, 2, gain)
    caption, audio_bytes, observed = '', 0, []
    async with connect('wss://api.openai.com/v1/realtime?model=' + session['model'], additional_headers={'Authorization': 'Bearer ' + session['value']}, open_timeout=20, max_size=4 * 1024 * 1024) as socket:
        await socket.send(json.dumps({'type': 'session.update', 'session': {'type': 'realtime', 'instructions': 'Essai technique sur un extrait public. Écoute puis répète la phrase française entendue, sans ajouter de commentaire.', 'tools': [], 'audio': {'input': {'format': {'type': 'audio/pcm', 'rate': 24000}, 'noise_reduction': None, 'turn_detection': None}}}}))
        async with asyncio.timeout(30):
            async for raw in socket:
                event = json.loads(raw)
                if event['type'] == 'error':
                    raise RuntimeError(event.get('error', {}).get('code', 'session_error'))
                if event['type'] == 'session.updated':
                    break
        await socket.send(json.dumps({'type': 'input_audio_buffer.append', 'audio': base64.b64encode(pcm).decode()}))
        await socket.send(json.dumps({'type': 'input_audio_buffer.commit'}))
        await socket.send(json.dumps({'type': 'response.create'}))
        async with asyncio.timeout(60):
            async for raw in socket:
                event = json.loads(raw)
                kind = event['type']
                if kind not in observed:
                    observed.append(kind)
                if kind == 'error':
                    raise RuntimeError(event.get('error', {}).get('code', 'audio_error'))
                if kind == 'response.output_audio_transcript.delta':
                    caption += event['delta']
                if kind == 'response.output_audio.delta':
                    audio_bytes += len(base64.b64decode(event['delta']))
                if kind == 'response.done':
                    assert event['response']['status'] == 'completed', event['response'].get('status')
                    break
    assert caption.strip() and audio_bytes > 0, {'caption': caption, 'audio_bytes': audio_bytes}
    recognized = any(word in caption.lower() for word in ['nations', 'pêcher', '2048'])
    result = {'status': 'passed' if recognized else 'failed_recognition', 'transport_verified': True, 'speech_recognized': recognized, 'mode': 'real_openai_audio', 'model': session['model'], 'public_audio_sample': sample.name, 'gain_applied': gain, 'personal_webcam_used': False, 'images_sent_to_openai': 0, 'audio_reply_bytes': audio_bytes, 'caption': caption, 'events': observed}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))
    assert recognized, 'Audio transport works but the public phrase was not recognized'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sample', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.sample, args.output))
