import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from maas import history, proofs
from maas.db import Base, Record
from maas.domain import quote, digest
from maas.organizations import sign_scope
from maas.purchase_proofs import record_lifecycle, check_source
from maas.security import USERS, token

@pytest.fixture
def setup(monkeypatch):
 monkeypatch.setenv('JWT_SECRET','history-tests-secret-01234567890123456789')
 engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
 Base.metadata.create_all(engine)
 factory=sessionmaker(engine,expire_on_commit=False)
 monkeypatch.setattr(history,'Session',factory)
 q=quote(USERS['lea'],['parking'],'app','2026-10-29')
 with factory.begin() as db:
  for oid,uid in [('mine','lea'),('older','lea'),('other','adult')]:
   db.add(Record(id=oid,kind='order',data={'id':oid,'org':'alize','traveler':uid,'quote':q,'state':'payment_pending','payment_count':0,'payment_mode':'local_simulator','refund_cents':0,'created_at':'2026-10-29T00:00:00+00:00','channel':'web'}))
 def get(db,rid,kind=None,lock=False):
  r=db.get(Record,rid)
  if not r or (kind and r.kind!=kind):raise HTTPException(404)
  return r
 app=FastAPI();history.register(app,get,None)
 with TestClient(app) as c:yield c,factory

def auth(uid='lea',selected=None):
 u=USERS[uid]
 return {'Authorization':'Bearer '+token(u),'X-MaaS-Coordination':sign_scope('maas-coordination',u,traveler=selected or (uid if uid in ('lea','adult') else None))}

def test_history_pagination_and_rights(setup):
 c,_=setup
 r=c.get('/api/assistant/purchases?limit=1',headers=auth()).json()
 assert r['total']==2 and len(r['purchases'])==1 and r['has_more']
 assert r['purchases'][0]['proof_status']=='not_available'
 assert c.get('/api/assistant/purchases?traveler_id=adult',headers=auth()).status_code==403
 assert c.get('/api/assistant/purchases?limit=30',headers=auth()).status_code==422
 assert c.get('/api/assistant/purchases',headers={'Authorization':auth()['Authorization']}).status_code==403
 assert c.get('/api/assistant/purchases',headers=auth('clerk','lea')).json()['total']==2
 assert c.get('/api/assistant/purchases',headers=auth('clerk')).status_code==422
 assert c.get('/api/assistant/purchases/other',headers=auth('clerk','lea')).status_code==403

def test_proofs_authorize_before_chain_access(setup,monkeypatch):
 c,_=setup
 def forbidden(*a):raise AssertionError('RPC should not run')
 monkeypatch.setattr(history,'verify_record',forbidden)
 assert c.get('/api/assistant/purchases/mine/proofs',headers=auth('adult')).status_code==403
 assert c.get('/api/assistant/purchases/mine/proofs',headers=auth()).json()['status']=='not_available'

def test_outbox_atomic_idempotent_and_detects_modified_source(setup,monkeypatch):
 c,factory=setup
 monkeypatch.setattr(proofs,'sign_manifest',lambda *a: (_ for _ in ()).throw(AssertionError('No signing on purchase path')))
 with factory.begin() as db:
  first=record_lifecycle(db,'order.confirmed',{'order_id':'mine'})
  assert record_lifecycle(db,'order.confirmed',{'order_id':'mine'})['id']==first['id']
  assert first['status']=='pending' and 'signature' not in first
  assert 'lea' not in json.dumps(first['manifest']) and 'amount_cents' not in json.dumps(first['manifest'])
 with factory() as db:assert len(list(db.scalars(select(Record).where(Record.kind=='proof'))))==1
 assert c.get('/api/assistant/purchases/mine/proofs',headers=auth()).json()['status']=='pending'
 with factory.begin() as db:
  row=db.get(Record,'mine');o=copy.deepcopy(row.data);o['quote']['total_cents']=999;row.data=o
 assert c.get('/api/assistant/purchases/mine/proofs',headers=auth()).json()['status']=='data_mismatch'
 with pytest.raises(RuntimeError):
  with factory.begin() as db:
   record_lifecycle(db,'order.confirmed',{'order_id':'older'})
   raise RuntimeError('rollback')
 with factory() as db:assert len(list(db.scalars(select(Record).where(Record.kind=='proof'))))==1

def test_verified_proofs_must_cover_every_business_source(setup,monkeypatch):
 c,factory=setup
 monkeypatch.setattr(history,'verify_record',lambda p:{'id':p['id'],'stage':p['stage'],'status':'verified'})
 with factory.begin() as db:
  row=db.get(Record,'mine');row.data={**row.data,'payment_count':1,'paid_at':'now','card':{'load_count':1},'refund_cents':100}
  db.add(Record(id='usage-1',kind='event',data={'data':{'order_id':'mine'}}))
  db.add(Record(id='usage-2',kind='event',data={'data':{'order_id':'mine'}}))
  db.add(Record(id='refund-1',kind='refund',data={'order_id':'mine','amount_cents':100}))
  for action,payload in [('order.confirmed',{}),('payment.confirmed.simulated',{}),('order.fulfilled',{}),('refund.recorded.simulated',{'id':'refund-1'}),('event.accepted',{'event_id':'usage-1'})]:
   record_lifecycle(db,action,{'order_id':'mine',**payload})
 partial=c.get('/api/assistant/purchases/mine/proofs',headers=auth()).json()
 assert partial['status']=='not_available' and partial['missing_sources']==[{'stage':'usage','id':'usage-2'}]
 with factory.begin() as db:record_lifecycle(db,'event.accepted',{'order_id':'mine','event_id':'usage-2'})
 assert c.get('/api/assistant/purchases/mine/proofs',headers=auth()).json()['status']=='verified'

def test_signature_and_live_chain_checks_do_not_trust_cached_verified(setup,tmp_path,monkeypatch):
 _,factory=setup
 monkeypatch.setenv('PROOF_KEY_PATH',str(tmp_path/'key'))
 with factory.begin() as db:p=copy.deepcopy(record_lifecycle(db,'order.confirmed',{'order_id':'mine'}))
 p.update(proofs.sign_manifest(p['manifest']));p['status']='anchored';p['chain']={'instance_id':'current','contract':'contract','verified':True}
 deployment=tmp_path/'deployment.json';deployment.write_text(json.dumps({'instance_id':'current','address':'contract','abi':[]}))
 monkeypatch.setattr(proofs,'Path',lambda x:deployment if str(x)=='/proofs/deployment.json' else Path(x))
 found=[bytes.fromhex(p['digest']),2,123]
 class W3:
  HTTPProvider=staticmethod(lambda *a,**kw:None)
  def __init__(self,*a):
   self.eth=SimpleNamespace(chain_id=31337,get_code=lambda *a:b'code',contract=lambda **kw:SimpleNamespace(functions=SimpleNamespace(proofs=lambda *a:SimpleNamespace(call=lambda:found))))
 monkeypatch.setattr(proofs,'Web3',W3)
 assert proofs.verify_record(p)['status']=='verified'
 found[0]=bytes.fromhex('00'*32)
 assert proofs.verify_record(p)['status']=='invalid'
 found[0]=bytes.fromhex(p['digest']);found[2]=0
 assert proofs.verify_record(p)['status']=='not_anchored'
 p['chain']['instance_id']='old'
 assert proofs.verify_record(p)['status']=='deployment_changed'
 p['chain']['instance_id']='current'
 monkeypatch.setattr(W3,'__init__',lambda *a: (_ for _ in ()).throw(ConnectionError()))
 assert proofs.verify_record(p)['status']=='chain_unavailable'
 p['manifest']['recorded_at']='modified'
 assert proofs.verify_record(p)['status']=='invalid'
