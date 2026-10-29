"""Bank orchestration: provider calls and Temporal are mocked, transaction states are real."""
from types import SimpleNamespace
import httpx
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from maas import integrations,bridge
from maas.db import Base,Record
from maas.security import USERS,token

@pytest.fixture
def setup(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    monkeypatch.setattr(integrations,'Session',factory)
    monkeypatch.setattr(bridge,'configured',lambda:True)
    monkeypatch.setattr(bridge,'payment_payload',lambda order:{'ref':order['id']})
    with factory.begin() as db:db.add(Record(id='o',kind='order',data={'id':'o','org':'alize','traveler':'lea','channel':'web','state':'payment_pending','payment_mode':'bridge_sandbox','payment_count':0,'quote':{'total_cents':1200}}))
    class Signals(list):
        fail=False
    signals=Signals()
    async def signal(name):
        signals.append(name)
        if signals.fail:raise ConnectionError('Temporal unavailable')
    async def temporal():return SimpleNamespace(get_workflow_handle=lambda _:SimpleNamespace(signal=signal))
    def get(db,rid,kind=None,lock=False):
        r=db.get(Record,rid)
        if not r:raise HTTPException(404)
        return r
    app=FastAPI();integrations.register(app,get,temporal,lambda *a:None)
    with TestClient(app) as client:yield client,factory,signals

def auth(uid='lea'):return {'Authorization':'Bearer '+token(USERS[uid])}

def test_ambiguous_bank_creation_is_never_reposted(setup,monkeypatch):
    c,f,signals=setup;calls=[]
    def create(payload):calls.append(payload);raise httpx.ReadTimeout('uncertain')
    monkeypatch.setattr(bridge,'create_payment',create)
    assert c.post('/api/orders/o/bridge',headers=auth()).status_code==502
    assert c.post('/api/orders/o/bridge',headers=auth()).status_code==409
    with f() as db:
        assert db.get(Record,'o').data['bridge']['status']=='unknown'
        assert db.get(Record,'o').data['payment_count']==0
    assert len(calls)==1 and not signals

def test_created_bank_link_is_reused_without_second_post(setup,monkeypatch):
    c,f,_=setup;calls=[]
    def create(payload):calls.append(payload);return {'id':'bank','url':'https://pay.bridgeapi.io/demo'}
    monkeypatch.setattr(bridge,'create_payment',create)
    assert c.post('/api/orders/o/bridge',headers=auth()).status_code==200
    assert c.post('/api/orders/o/bridge',headers=auth()).status_code==200
    assert len(calls)==1

@pytest.mark.parametrize('settled',[False,True])
def test_polling_persists_payment_once_and_stops_signaling_after_delivery(setup,monkeypatch,settled):
    c,f,signals=setup
    with f.begin() as db:
        r=db.get(Record,'o');r.data={**r.data,'bridge':{'id':'bank','status':'created'}}
    monkeypatch.setattr(bridge,'read_payment',lambda *a:{'id':'bank','status':'ACSC' if settled else 'PDNG'})
    monkeypatch.setattr(bridge,'settled_for_order',lambda *a:settled)
    for _ in range(2):assert c.post('/api/orders/o/bridge/status',headers=auth()).status_code==200
    with f() as db:assert db.get(Record,'o').data['payment_count']==int(settled)
    assert len(signals)==(2 if settled else 0)
    if settled:
        with f.begin() as db:
            r=db.get(Record,'o');r.data={**r.data,'state':'fulfilled'}
        assert c.post('/api/orders/o/bridge/status',headers=auth()).status_code==200
        assert len(signals)==2

def test_other_traveler_cannot_trigger_bank_creation(setup,monkeypatch):
    c,f,signals=setup
    def forbidden(*a):raise AssertionError('Must authorize before provider call')
    monkeypatch.setattr(bridge,'create_payment',forbidden)
    assert c.post('/api/orders/o/bridge',headers=auth('adult')).status_code==403


def test_bank_confirmation_survives_lost_signal_without_second_payment(setup,monkeypatch):
    c,f,signals=setup
    with f.begin() as db:
        r=db.get(Record,'o');r.data={**r.data,'bridge':{'id':'bank','status':'created'}}
    monkeypatch.setattr(bridge,'read_payment',lambda *a:{'id':'bank','status':'ACSC'})
    monkeypatch.setattr(bridge,'settled_for_order',lambda *a:True)
    signals.fail=True
    assert c.post('/api/orders/o/bridge/status',headers=auth()).status_code==503
    with f() as db:
        first=db.get(Record,'o').data
        assert first['payment_count']==1
    signals.fail=False
    assert c.post('/api/orders/o/bridge/status',headers=auth()).status_code==200
    with f() as db:
        again=db.get(Record,'o').data
        assert again['payment_count']==1 and again['paid_at']==first['paid_at']
    assert len(signals)==2


def test_unavailable_bank_status_never_unlocks_order(setup,monkeypatch):
    c,f,signals=setup
    with f.begin() as db:
        r=db.get(Record,'o');r.data={**r.data,'bridge':{'id':'bank','status':'created'}}
    def down(*a):raise httpx.ConnectError('bank unavailable')
    monkeypatch.setattr(bridge,'read_payment',down)
    assert c.post('/api/orders/o/bridge/status',headers=auth()).status_code==503
    with f() as db:assert db.get(Record,'o').data['payment_count']==0
    assert not signals
