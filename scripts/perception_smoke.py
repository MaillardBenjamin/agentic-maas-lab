"""Real-model API smoke. Pass a public, already mouth-cropped video with audio."""
import argparse
import json
import os
from pathlib import Path
import time
import httpx

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('video', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
base = os.environ.get('API_URL', 'http://api:8000')
with httpx.Client(base_url=base, timeout=30) as client:
    token = client.post('/api/demo/login/lea').json()['access_token']
    other = client.post('/api/demo/login/adult').json()['access_token']
    auth = {'Authorization': 'Bearer ' + token}
    foreign = {'Authorization': 'Bearer ' + other}
    health = client.get('/api/perception/status', headers=auth).json()
    assert health.get('ready'), health
    results = {'engine_status': health, 'tests': []}
    for mode in ['avsr', 'vsr']:
        started = time.monotonic()
        response = client.post('/api/perception/jobs', params={'mode': mode, 'framing': 'mouth', 'language': 'fr'}, content=args.video.read_bytes(), headers={**auth, 'Content-Type': 'video/mp4', 'X-Capture-Consent': 'true'})
        assert response.status_code == 202, response.text
        path = '/api/perception/jobs/' + response.json()['id']
        assert client.get(path, headers=foreign).status_code == 404
        assert client.delete(path, headers=foreign).status_code == 404
        while time.monotonic() - started < 320:
            value = client.get(path, headers=auth).json()
            if value['status'] in {'failed', 'completed'}:
                break
            time.sleep(1)
        assert value['status'] == 'completed', value
        result = value['result']
        assert result['mode'] == 'real_model' and result['video_used'] is True
        assert result['audio_used'] is (mode == 'avsr') and result['modality'] == mode
        assert result['requires_confirmation'] and result['text']
        assert client.delete(path, headers=auth).status_code == 200
        assert client.get(path, headers=auth).status_code == 404
        result['http_elapsed_seconds'] = round(time.monotonic() - started, 2)
        results['tests'].append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2))
