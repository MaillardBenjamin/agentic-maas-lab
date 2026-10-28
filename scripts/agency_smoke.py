"""Agency/CRC local lifecycle; financial effects and card hardware remain simulated."""
import json
from pathlib import Path
import time
import uuid

import httpx

base = 'http://api:8000'
prefix = 'agency-smoke-' + uuid.uuid4().hex
with httpx.Client(base_url=base, timeout=30) as client:
    staff = {'Authorization': 'Bearer ' + client.post('/api/demo/login/clerk').json()['access_token']}
    traveler = {'Authorization': 'Bearer ' + client.post('/api/demo/login/lea').json()['access_token']}
    assert client.get('/api/agency/cases', headers=traveler).status_code == 403
    quote = client.post('/api/quotes', headers=staff, json={'traveler': 'lea', 'seller': 'agency', 'products': ['transport'], 'travel_date': '2026-10-28'})
    quote.raise_for_status()
    assert quote.json()['total_cents'] == 700
    response = client.post('/api/orders', headers=staff, json={'quote_id': quote.json()['id'], 'channel': 'agency', 'payment_mode': 'local_simulator', 'pause_before_issue': False, 'idempotency_key': prefix + '-sale'})
    response.raise_for_status()
    oid = response.json()['id']
    assert client.post('/api/demo/orders/' + oid + '/pay', headers=staff).status_code == 200
    for _ in range(40):
        order = client.get('/api/orders/' + oid, headers=staff).json()
        if order['state'] == 'fulfilled':
            break
        time.sleep(.5)
    assert order['state'] == 'fulfilled' and order['card']['sdk']['verified_read_after_write']
    body = {'traveler': 'lea', 'order_id': oid, 'channel': 'phone', 'motive': 'delivery', 'summary': 'Démonstration CRC : vérifier le titre et expliquer la régularisation.', 'idempotency_key': prefix + '-contact'}
    response = client.post('/api/agency/cases', headers=staff, json=body)
    response.raise_for_status()
    contact = response.json()
    assert client.post('/api/agency/cases', headers=staff, json=body).json()['id'] == contact['id']
    denied = client.post('/api/orders/' + oid + '/refunds', headers=staff, json={'amount_cents': 600, 'reason': 'Vérification du dépassement de délégation', 'idempotency_key': prefix + '-denied'})
    assert denied.status_code == 403
    refund_body = {'amount_cents': 200, 'reason': 'Régularisation de démonstration vérifiée par le conseiller', 'idempotency_key': prefix + '-refund'}
    refund = client.post('/api/orders/' + oid + '/refunds', headers=staff, json=refund_body)
    refund.raise_for_status()
    assert client.post('/api/orders/' + oid + '/refunds', headers=staff, json=refund_body).json()['id'] == refund.json()['id']
    order = client.get('/api/orders/' + oid, headers=staff).json()
    assert order['refund_cents'] == 200 and order['payment_count'] == 1
    update = {'revision': contact['revision'], 'status': 'resolved', 'note': 'Titre délivré et relu sur carte stub. Régularisation simulée de 2 € enregistrée ; aucun remboursement bancaire exécuté.', 'idempotency_key': prefix + '-close'}
    path = '/api/agency/cases/' + contact['id']
    closed = client.post(path + '/updates', headers=staff, json=update)
    closed.raise_for_status()
    assert closed.json()['status'] == 'resolved'
    assert client.post(path + '/updates', headers=staff, json=update).json()['revision'] == 2
    stored = client.get(path, headers=staff).json()
    assert len(stored['notes']) == 2
    evidence = {'status': 'passed', 'order_id': oid, 'case_id': stored['id'], 'channel': stored['channel'], 'case_status': stored['status'], 'notes_persisted': len(stored['notes']), 'agency_quote_cents': quote.json()['total_cents'], 'verified_stub_delivery': True, 'clerk_over_5_euros_refused': True, 'refund_cents_after_replay': order['refund_cents'], 'traveler_case_access_refused': True, 'bank_refund_executed': False}
    output = Path('/evidence/agency-crc.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(json.dumps(evidence, ensure_ascii=False))
