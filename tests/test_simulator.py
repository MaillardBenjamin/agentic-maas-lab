"""Stateful card adapter with its own isolated SQLite ledger; no hardware/network."""
import importlib
import sys
import httpx
import pytest
from fastapi.testclient import TestClient
from maas.observability import service_headers

@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setenv('CARD_DB',str(tmp_path/'cards.db'))
    sys.modules.pop('maas.simulator',None)
    module=importlib.import_module('maas.simulator');calls=[]
    def sdk(*a,**kw):
        calls.append(kw['json']['operation_id'])
        return httpx.Response(200,request=httpx.Request('POST','http://keyple/load'),json={'verified_read_after_write':True})
    monkeypatch.setattr(module.httpx,'post',sdk)
    with TestClient(module.app) as client:yield client,module,calls

def test_load_replay_and_conflicting_identity(setup):
    c,m,calls=setup;body={'operation_id':'op','order_id':'order'};h=service_headers()
    first=c.post('/cards/load',headers=h,json=body)
    assert first.status_code==200 and not first.json()['reconciled']
    assert c.post('/cards/load',headers=h,json=body).json()['reconciled']
    assert calls==['op']
    assert c.post('/cards/load',headers=h,json={**body,'order_id':'other'}).status_code==409
    assert c.get('/cards',headers=h).json()[0]['load_count']==1

def test_lost_response_commits_once_then_recovers_from_ledger(setup):
    c,m,calls=setup;h=service_headers();body={'operation_id':'op','order_id':'order'}
    assert c.post('/faults/lose-response',headers=h).status_code==200
    assert c.post('/cards/load',headers=h,json=body).status_code==503
    assert c.get('/cards',headers=h).json()[0]['load_count']==1
    again=c.post('/cards/load',headers=h,json=body)
    assert again.status_code==200 and again.json()['reconciled'] and calls==['op']

def test_unavailable_sdk_has_no_confirmed_load_and_can_retry(setup,monkeypatch):
    c,m,calls=setup;h=service_headers();body={'operation_id':'op','order_id':'order'}
    original=m.httpx.post
    def unavailable(*a,**kw):raise httpx.ConnectError('down')
    monkeypatch.setattr(m.httpx,'post',unavailable)
    assert c.post('/cards/load',headers=h,json=body).status_code==503
    assert c.get('/cards',headers=h).json()==[]
    monkeypatch.setattr(m.httpx,'post',original)
    assert c.post('/cards/load',headers=h,json=body).status_code==200
    assert len(calls)==1

def test_service_auth_and_input_validation(setup):
    c,m,calls=setup
    assert c.post('/cards/load',json={'operation_id':'op','order_id':'o'}).status_code==403
    assert c.post('/cards/load',headers=service_headers(),json={'operation_id':123,'order_id':'o'}).status_code==422
    assert not calls
