import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from maas import agency
from maas.db import Base, Record
from maas.security import USERS, token


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(agency, 'Session', factory)
    with factory.begin() as db:
        db.add(Record(id='lea-order', kind='order', data={'org': 'alize', 'traveler': 'lea'}))
        db.add(Record(id='alex-order', kind='order', data={'org': 'alize', 'traveler': 'adult'}))
        db.add(Record(id='foreign-order', kind='order', data={'org': 'other', 'traveler': 'lea'}))
    logs = []
    app = FastAPI()
    agency.register(app, lambda db, action, payload: logs.append((action, payload)))
    with TestClient(app) as client:
        yield client, factory, logs
    engine.dispose()


def auth(identity='clerk', org=None):
    user = USERS[identity] if org is None else {**USERS[identity], 'org': org}
    return {'Authorization': 'Bearer ' + token(user)}


def body(**updates):
    return {'traveler': 'lea', 'order_id': 'lea-order', 'channel': 'phone', 'motive': 'delivery', 'summary': 'Vérification du titre en démonstration', 'idempotency_key': 'contact-unit-test', **updates}


def test_staff_only_case_access(setup):
    client, _, _ = setup
    assert client.get('/api/agency/cases').status_code == 401
    for identity in ('lea', 'adult', 'demo'):
        assert client.get('/api/agency/cases', headers=auth(identity)).status_code == 403
        assert client.post('/api/agency/cases', headers=auth(identity), json=body()).status_code == 403
    assert client.get('/api/agency/cases', headers=auth('supervisor')).status_code == 200


def test_customer_order_binding_and_payload_validation(setup):
    client, _, _ = setup
    for payload, status in [(body(traveler='clerk'), 422), (body(order_id='alex-order'), 422), (body(order_id='foreign-order'), 404), (body(order_id='missing'), 404), (body(channel='video-call'), 422), (body(summary='  '), 422), (body(status='resolved'), 422)]:
        assert client.post('/api/agency/cases', headers=auth(), json=payload).status_code == status
    assert client.get('/api/agency/cases', headers=auth()).json() == []


def test_creation_replay_is_one_case_and_one_audit(setup):
    client, factory, logs = setup
    first = client.post('/api/agency/cases', headers=auth(), json=body()).json()
    replay = client.post('/api/agency/cases', headers=auth(), json=body()).json()
    assert first['id'] == replay['id'] and first['revision'] == 1
    assert first['assigned_to'] == 'clerk' and first['channel'] == 'phone'
    assert len(first['notes']) == 1
    assert client.post('/api/agency/cases', headers=auth(), json=body(summary='Une autre demande')).status_code == 409
    assert len(client.get('/api/agency/cases', headers=auth()).json()) == 1
    assert len(logs) == 1
    with factory() as db:
        assert len(list(db.scalars(select(Record).where(Record.kind == 'agency_case')))) == 1


def test_notes_status_replay_and_optimistic_concurrency(setup):
    client, _, _ = setup
    created = client.post('/api/agency/cases', headers=auth(), json=body()).json()
    path = '/api/agency/cases/' + created['id'] + '/updates'
    pending = {'revision': 1, 'status': 'pending', 'note': 'Vérification à effectuer.', 'idempotency_key': 'contact-update-pending'}
    assert client.post(path, headers=auth(), json=pending).json()['revision'] == 2
    assert client.post(path, headers=auth(), json=pending).json()['revision'] == 2
    stale = {**pending, 'idempotency_key': 'other-agent-update'}
    assert client.post(path, headers=auth('supervisor'), json=stale).status_code == 409
    assert client.post(path, headers=auth(), json={**pending, 'revision': 2, 'status': 'resolved', 'note': '', 'idempotency_key': 'empty-closure'}).status_code == 422
    closed = client.post(path, headers=auth('supervisor'), json={'revision': 2, 'status': 'resolved', 'note': 'Titre vérifié, réponse apportée.', 'idempotency_key': 'contact-update-closed'}).json()
    assert closed['status'] == 'resolved' and closed['revision'] == 3 and len(closed['notes']) == 3
    assert closed['notes'][-1]['author'] == 'supervisor'
    stored = client.get('/api/agency/cases/' + created['id'], headers=auth()).json()
    assert stored['notes'] == closed['notes']


def test_organization_isolation_for_read_and_update(setup):
    client, _, _ = setup
    created = client.post('/api/agency/cases', headers=auth(), json=body()).json()
    assert client.get('/api/agency/cases', headers=auth(org='other')).json() == []
    path = '/api/agency/cases/' + created['id']
    assert client.get(path, headers=auth('supervisor', 'other')).status_code == 404
    assert client.post(path + '/updates', headers=auth(org='other'), json={'revision': 1, 'note': 'Foreign note', 'idempotency_key': 'foreign-update'}).status_code == 404
