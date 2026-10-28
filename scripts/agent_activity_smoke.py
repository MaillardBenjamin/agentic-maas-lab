"""Real local LLM + A2A/MCP, with events observed before response completion."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import time

import httpx
from maas.ai import chat_backend

if chat_backend() != 'ollama_local':
    raise SystemExit('Sélectionnez Ollama local avant ce test ; aucun appel modèle lancé.')

base = os.environ.get('API_URL', 'http://api:8000')
with httpx.Client(base_url=base, timeout=610) as client:
    lea = {'Authorization': 'Bearer ' + client.post('/api/demo/login/lea').json()['access_token']}
    adult = {'Authorization': 'Bearer ' + client.post('/api/demo/login/adult').json()['access_token']}
    before = client.get('/api/agent-activity', headers=lea).json()
    cursor, seen, live = before['cursor'], [], False
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, '/api/chat', headers=lea, json={'message': 'Explique le tarif étudiant à 7 euros. Consulte le catalogue et les sources.', 'agent': 'conversation'})
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            response = client.get('/api/agent-activity?after=' + str(cursor), headers=lea)
            response.raise_for_status()
            snapshot = response.json()
            cursor = snapshot['cursor']
            seen.extend(snapshot['events'])
            if not future.done() and any(event['state'] == 'started' for event in snapshot['events']):
                live = True
            if future.done():
                break
            time.sleep(.25)
        reply = future.result()
        reply.raise_for_status()
        final = client.get('/api/agent-activity?after=' + str(cursor), headers=lea).json()
        seen.extend(final['events'])
    answer = reply.json()
    assert answer['mode'] == 'ollama_local', 'Select local inference before this smoke'
    rid = answer['activity_run_id']
    events = [event for event in seen if event['run_id'] == rid]
    pairs = {(event['protocol'], event['source'], event['target'], event['state']) for event in events}
    assert live, 'No event observed before the response finished'
    for protocol, source, target in [('A2A', 'interface', 'conversation'), ('A2A', 'conversation', 'tariffs'), ('A2A', 'tariffs', 'transport'), ('MCP', 'transport', 'read_provider_context')]:
        assert (protocol, source, target, 'started') in pairs, (protocol, source, target, events)
        assert (protocol, source, target, 'completed') in pairs, (protocol, source, target, events)
    foreign = client.get('/api/agent-activity', headers=adult).json()
    assert rid not in {run['id'] for run in foreign['runs']}
    assert not any(event['run_id'] == rid for event in foreign['events'])
    result = {'status': 'passed', 'mode': answer['mode'], 'model': answer['model'], 'events_observed_before_answer': live, 'events': events, 'other_traveler_isolated': True}
    path = Path('/evidence/agent-activity-local.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False), flush=True)
