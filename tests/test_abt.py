from datetime import date, datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from maas import abt
from maas.db import Base, Record
from maas.security import USERS, token
from maas.organizations import sign_scope

@pytest.fixture
def setup(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    monkeypatch.setattr(abt,'Session',factory);monkeypatch.setattr(abt,'utc_now',lambda:datetime(2026,1,31,16,tzinfo=timezone.utc))
    app=FastAPI();abt.register(app)
    with TestClient(app) as c:yield c,factory,monkeypatch

def auth(uid='lea'):
    return {'Authorization':'Bearer '+token(USERS[uid])}

def subscribe(c,product='transport_annual',key='test-annual-001',uid='lea',**extra):
    return c.post('/api/abt/subscriptions',headers=auth(uid),json={'traveler':uid,'product':product,'start_date':'2026-01-31','consent':True,'idempotency_key':key,**extra})

def snapshot(c):return c.get('/api/abt',headers=auth()).json()

def bill(factory):
    with factory.begin() as db:abt.billing(db)

def test_annual_schedule_calendar_and_idempotency(setup):
    c,f,_=setup
    first=subscribe(c);assert first.status_code==200,first.text
    assert subscribe(c).json()['id']==first.json()['id']
    data=snapshot(c);invoices=sorted(data['invoices'],key=lambda i:i['due_date'])
    assert len(invoices)==12 and sum(i['amount_cents'] for i in invoices)==60000
    assert invoices[1]['due_date']=='2026-02-28' and invoices[2]['due_date']=='2026-03-31'
    assert first.json()['end_date']=='2027-01-31'
    ride=c.post('/api/demo/abt/'+first.json()['id']+'/validate',headers=auth(),json={'passage_id':'annual-ride','occurred_at':'2026-01-31T12:00:00Z'})
    assert ride.status_code==200 and ride.json()['charge_cents']==0
    assert subscribe(c,product='transport_postpaid').status_code==409
    assert subscribe(c,key='another-key').status_code==409
    bill(f);bill(f)
    assert sum(i['status']=='paid_simulated' for i in snapshot(c)['invoices'])==1

def test_consent_dates_and_access(setup):
    c,_,_=setup
    assert subscribe(c,consent=False).status_code==422
    assert subscribe(c,start_date='2026-01-30').status_code==422
    assert subscribe(c,traveler='adult').status_code==403
    assert subscribe(c).status_code==200
    cid=snapshot(c)['contracts'][0]['id']
    assert c.get('/api/abt?traveler=lea',headers=auth('adult')).status_code==403
    assert c.get('/api/assistant/abt',headers=auth()).status_code==403
    assert c.get('/api/abt?traveler=lea',headers=auth('clerk')).status_code==200
    signed=sign_scope('maas-coordination',USERS['clerk'],traveler='lea')
    assert c.get('/api/assistant/abt',headers={**auth('clerk'),'X-MaaS-Coordination':signed}).status_code==200
    assert c.post('/api/demo/abt/'+cid+'/validate',headers=auth('adult'),json={'passage_id':'x','occurred_at':'2026-01-31T12:00:00Z'}).status_code==403

def test_postpaid_cap_dedup_period_closure_and_collection(setup):
    c,f,mp=setup
    cid=subscribe(c,'transport_postpaid').json()['id']
    def use(i,at='2026-01-31T12:00:00Z'):
        return c.post('/api/demo/abt/'+cid+'/validate',headers=auth(),json={'passage_id':str(i),'occurred_at':at})
    for i in range(35):assert use(i).status_code==200
    assert use(0).json()['duplicate']
    assert use(0,'2026-01-31T13:00:00Z').status_code==409
    assert sum(u['charge_cents'] for u in snapshot(c)['usages'])==6000
    bill(f);assert not snapshot(c)['invoices']
    mp.setattr(abt,'utc_now',lambda:datetime(2026,2,1,16,tzinfo=timezone.utc));bill(f);bill(f)
    invoice=snapshot(c)['invoices'];assert len(invoice)==1 and invoice[0]['amount_cents']==6000 and invoice[0]['status']=='paid_simulated'
    assert use('late').status_code==409
    assert use('feb','2026-02-01T12:00:00Z').json()['charge_cents']==200

def test_failed_debit_suspends_then_retry_restores_right(setup):
    c,f,_=setup
    cid=subscribe(c).json()['id'];invoice=min(snapshot(c)['invoices'],key=lambda i:i['due_date'])
    path='/api/demo/abt/invoices/'+invoice['id']+'/collect'
    assert c.post(path,headers=auth(),json={'failed':True}).json()['status']=='failed'
    assert snapshot(c)['contracts'][0]['status']=='suspended'
    assert c.post('/api/demo/abt/'+cid+'/validate',headers=auth(),json={'passage_id':'x','occurred_at':'2026-01-31T12:00:00Z'}).status_code==409
    assert c.post(path,headers=auth(),json={'failed':False}).json()['status']=='paid_simulated'
    assert snapshot(c)['contracts'][0]['status']=='active'
    assert c.post(path,headers=auth(),json={'failed':True}).json()['status']=='paid_simulated'
    future=max(snapshot(c)['invoices'],key=lambda i:i['due_date'])
    assert c.post('/api/demo/abt/invoices/'+future['id']+'/collect',headers=auth(),json={}).status_code==409

def test_future_and_expired_rights_refuse_usage(setup):
    c,f,mp=setup
    cid=subscribe(c).json()['id']
    for at in ['2026-01-30T10:00:00Z','2027-01-31T10:00:00Z','2030-01-01T00:00:00Z','2026-01-31T10:00:00']:
        assert c.post('/api/demo/abt/'+cid+'/validate',headers=auth(),json={'passage_id':at,'occurred_at':at}).status_code in (409,422)
    mp.setattr(abt,'utc_now',lambda:datetime(2027,1,31,16,tzinfo=timezone.utc));bill(f)
    assert snapshot(c)['contracts'][0]['status']=='expired'
    assert len(snapshot(c)['invoices'])==12

def test_known_purchases_and_abt_titles_share_the_same_account(setup):
    c,f,_=setup
    with f.begin() as db:
        db.add(Record(id='old-known-order',kind='order',data={'id':'old-known-order','traveler':'lea','org':'alize','state':'fulfilled','created_at':'2026-01-01T00:00:00Z','quote':{'lines':[{'name':'Transport'}],'total_cents':700}}))
    bill(f)
    data=snapshot(c)
    assert data['orders'][0]['account_id']==data['id']
    sub=subscribe(c).json();assert sub['account_id']==data['id']
    assert all(i['account_id']==data['id'] for i in snapshot(c)['invoices'])
    with f() as db:
        assert db.get(Record,'old-known-order').data['account_id']==data['id']
        assert len(list(db.scalars(select(Record).where(Record.kind=='abt_account'))))==1


def advance(mp, value):
    mp.setattr(abt, 'utc_now', lambda: datetime.fromisoformat(value.replace('Z','+00:00')))


def test_validation_boundaries_use_the_same_clock_as_billing(setup):
    c,f,mp=setup
    cid=subscribe(c).json()['id']
    def use(key,at):return c.post('/api/demo/abt/'+cid+'/validate',headers=auth(),json={'passage_id':key,'occurred_at':at})
    assert use('start','2026-01-31T00:00:00Z').status_code==200
    assert use('future','2026-01-31T16:00:01Z').status_code==409
    advance(mp,'2027-01-31T16:00:00Z')
    assert use('end','2027-01-31T00:00:00Z').status_code==409
    assert use('last','2027-01-30T23:59:59Z').status_code==200
    # Re-delivery remains idempotent after the entitlement expires.
    bill(f)
    assert use('start','2026-01-31T00:00:00Z').json()['duplicate']


def test_multiple_arrears_and_attempt_history(setup):
    c,f,mp=setup
    subscribe(c);advance(mp,'2026-03-31T16:00:00Z')
    invoices=snapshot(c)['invoices'][:3]
    def debit(i,failed):return c.post('/api/demo/abt/invoices/'+i['id']+'/collect',headers=auth(),json={'failed':failed})
    for i in invoices[:2]:assert debit(i,True).status_code==200
    assert debit(invoices[0],False).status_code==200
    assert snapshot(c)['contracts'][0]['status']=='suspended'
    assert debit(invoices[1],False).status_code==200
    assert snapshot(c)['contracts'][0]['status']=='active'
    old=snapshot(c)['invoices'][0]
    assert [a['status'] for a in old['attempts']]==['failed','paid_simulated']
    assert debit(old,False).json()['attempts']==old['attempts']
    advance(mp,'2027-02-01T16:00:00Z')
    assert debit(invoices[2],True).status_code==200
    assert snapshot(c)['contracts'][0]['status']=='expired'


def test_all_twelve_installments_are_collected_once_after_downtime(setup):
    c,f,mp=setup
    subscribe(c);advance(mp,'2027-01-31T16:00:00Z');bill(f);bill(f)
    invoices=snapshot(c)['invoices']
    assert len(invoices)==12 and sum(i['amount_cents'] for i in invoices)==60000
    assert all(i['status']=='paid_simulated' and len(i['attempts'])==1 for i in invoices)
    assert snapshot(c)['contracts'][0]['status']=='expired'


def test_accepted_terms_survive_catalog_change(setup):
    import copy
    c,f,mp=setup
    cid=subscribe(c,'transport_postpaid').json()['id']
    altered=copy.deepcopy(abt.CATALOG)
    altered['abt_products'][1]['ride_cents']=999
    altered['abt_products'][1]['monthly_cap_cents']=100000
    mp.setattr(abt,'CATALOG',altered)
    r=c.post('/api/demo/abt/'+cid+'/validate',headers=auth(),json={'passage_id':'snapshot','occurred_at':'2026-01-31T12:00:00Z'})
    assert r.json()['charge_cents']==200
    assert snapshot(c)['contracts'][0]['terms']['monthly_cap_cents']==6000


@pytest.mark.parametrize('identity',['lea','clerk'])
def test_mutated_idempotency_key_rolls_back_and_adjacent_contract_allowed(setup,identity):
    c,f,mp=setup
    body={'traveler':'lea','product':'transport_annual','start_date':'2026-01-31','consent':True,'idempotency_key':'actor-key-123'}
    first=c.post('/api/abt/subscriptions',headers=auth(identity),json=body)
    assert first.status_code==200
    assert c.post('/api/abt/subscriptions',headers=auth(identity),json={**body,'product':'transport_postpaid'}).status_code==409
    assert len(snapshot(c)['contracts'])==1 and len(snapshot(c)['invoices'])==12
    assert c.post('/api/abt/subscriptions',headers=auth(identity),json={**body,'start_date':'2027-01-31','product':'transport_postpaid','idempotency_key':'next-key-123'}).status_code==200
    assert len(snapshot(c)['contracts'])==2


def test_access_denied_before_debit_and_service_endpoint_protected(setup):
    c,f,mp=setup
    sub=subscribe(c).json();i=snapshot(c)['invoices'][0]
    assert c.get('/api/abt').status_code==401
    assert c.post('/internal/abt/billing').status_code==403
    assert c.post('/api/demo/abt/invoices/'+i['id']+'/collect',headers=auth('adult'),json={}).status_code==403
    signed=sign_scope('maas-coordination',USERS['clerk'],traveler='lea')
    assert c.get('/api/assistant/abt',headers={**auth('adult'),'X-MaaS-Coordination':signed}).status_code==403
    foreign={**USERS['clerk'],'org':'other'}
    assert c.get('/api/abt?traveler=lea',headers={'Authorization':'Bearer '+token(foreign)}).status_code==403
    assert all(i['status']=='pending' for i in snapshot(c)['invoices'])


def test_subscription_and_installments_are_atomic(setup,monkeypatch):
    c,f,mp=setup
    original=abt.invoice
    def fail(db,contract,period,*args):
        original(db,contract,period,*args)
        if period=='4':raise RuntimeError('Interrupted schedule')
    monkeypatch.setattr(abt,'invoice',fail)
    with pytest.raises(RuntimeError):subscribe(c)
    with f() as db:
        assert not list(db.scalars(select(Record).where(Record.kind.in_(['abt_contract','abt_invoice','abt_account']))))


@pytest.mark.parametrize('channel',['web','automate','agency'])
def test_backfill_is_idempotent_keeps_order_state_and_excludes_foreign_unknown(setup,channel):
    c,f,mp=setup
    def order(oid,traveler='lea',org='alize'):
        return Record(id=oid,kind='order',data={'id':oid,'org':org,'traveler':traveler,'channel':channel,'state':'payment_pending','created_at':'2026-01-01','quote':{'lines':[],'total_cents':500}})
    with f.begin() as db:db.add_all([order('known'),order('unknown','guest'),order('foreign','lea','other')])
    bill(f);bill(f)
    with f() as db:
        assert db.get(Record,'known').data['account_id']=='abt-account-alize-lea'
        assert db.get(Record,'known').data['state']=='payment_pending'
        assert 'account_id' not in db.get(Record,'unknown').data
        assert 'account_id' not in db.get(Record,'foreign').data
        assert len(list(db.scalars(select(Record).where(Record.kind=='abt_account'))))==1


def test_postpaid_utc_month_boundary_and_empty_month(setup):
    c,f,mp=setup
    cid=subscribe(c,'transport_postpaid').json()['id']
    def use(key,at):return c.post('/api/demo/abt/'+cid+'/validate',headers=auth(),json={'passage_id':key,'occurred_at':at})
    advance(mp,'2026-02-01T01:00:00Z')
    # 00:30 +01:00 is still January in the billing timezone.
    assert use('jan','2026-02-01T00:30:00+01:00').json()['period']=='2026-01'
    assert use('feb','2026-02-01T00:00:00Z').json()['period']=='2026-02'
    bill(f)
    assert [(i['period'],i['amount_cents']) for i in snapshot(c)['invoices']]==[('2026-01',200)]
    advance(mp,'2026-04-01T01:00:00Z');bill(f)
    assert [(i['period'],i['amount_cents']) for i in snapshot(c)['invoices']]==[('2026-01',200),('2026-02',200)]


@pytest.mark.parametrize('channel,actor',[('web','lea'),('automate','clerk'),('agency','clerk')])
def test_purchase_endpoint_attaches_beneficiary_not_seller_atomically(setup,channel,actor,monkeypatch):
    from maas import api as business
    from types import SimpleNamespace
    c,f,mp=setup
    monkeypatch.setattr(business,'Session',f)
    async def start(*a,**kw):pass
    async def temporal():return SimpleNamespace(start_workflow=start)
    monkeypatch.setattr(business,'temporal',temporal)
    api=TestClient(business.app)  # No service startup: DB and Temporal isolated above.
    q=api.post('/api/quotes',headers=auth(actor),json={'traveler':'lea','products':['transport'],'seller':'app' if actor=='lea' else 'agency','travel_date':'2026-01-31'})
    assert q.status_code==200,q.text
    body={'quote_id':q.json()['id'],'channel':channel,'idempotency_key':'purchase-'+channel}
    r=api.post('/api/orders',headers=auth(actor),json=body)
    assert r.status_code==200,r.text
    assert r.json()['account_id']=='abt-account-alize-lea'
    assert r.json()['traveler']=='lea'
    assert api.post('/api/orders',headers=auth(actor),json=body).json()['id']==r.json()['id']
    with f() as db:
        assert len(list(db.scalars(select(Record).where(Record.kind=='order'))))==1
        assert len(list(db.scalars(select(Record).where(Record.kind=='abt_account'))))==1


def test_billing_failure_rolls_back_whole_batch_and_retry_is_once(setup,monkeypatch):
    c,f,mp=setup
    subscribe(c);advance(mp,'2026-03-31T16:00:00Z')
    original=abt.collect;calls=[]
    def interrupted(db,row,*a):
        result=original(db,row,*a);calls.append(row.id)
        if len(calls)==2:raise RuntimeError('Worker interrupted')
        return result
    with monkeypatch.context() as m:
        m.setattr(abt,'collect',interrupted)
        with pytest.raises(RuntimeError):bill(f)
    assert all(i['status']=='pending' and not i.get('attempts') for i in snapshot(c)['invoices'])
    bill(f);bill(f)
    assert sum(i['status']=='paid_simulated' for i in snapshot(c)['invoices'])==3
    assert all(len(i.get('attempts',[]))<=1 for i in snapshot(c)['invoices'])


@pytest.mark.parametrize('start,offset,expected',[('2028-01-31',1,'2028-02-29'),('2028-02-29',12,'2029-02-28'),('2026-12-31',2,'2027-02-28')])
def test_calendar_leap_year_and_year_rollover(start,offset,expected):
    assert abt.month(date.fromisoformat(start),offset).isoformat()==expected


def test_old_abt_children_backfill_and_internal_service_billing(setup):
    from maas.observability import service_headers
    c,f,mp=setup
    sub=subscribe(c).json()
    with f.begin() as db:
        for r in db.scalars(select(Record).where(Record.kind.in_(['abt_contract','abt_invoice']))):
            r.data={k:v for k,v in r.data.items() if k!='account_id'}
    assert c.post('/internal/abt/billing',headers=service_headers()).status_code==200
    assert all(i['account_id']=='abt-account-alize-lea' for i in snapshot(c)['invoices'])
    assert snapshot(c)['contracts'][0]['account_id']=='abt-account-alize-lea'
    assert sum(i['status']=='paid_simulated' for i in snapshot(c)['invoices'])==1


def test_unknown_references_and_customer_do_not_create_effects(setup):
    c,f,_=setup
    assert c.get('/api/abt',headers=auth('clerk')).status_code==422
    assert c.get('/api/abt?traveler=unknown',headers=auth('clerk')).status_code==422
    assert c.post('/api/demo/abt/missing/validate',headers=auth(),json={'passage_id':'x','occurred_at':'2026-01-31T12:00:00Z'}).status_code==404
    assert c.post('/api/demo/abt/invoices/missing/collect',headers=auth(),json={}).status_code==404
    assert not snapshot(c)['contracts'] and not snapshot(c)['invoices']


def test_future_subscription_does_not_authorize_usage_before_start(setup):
    c,f,mp=setup
    cid=subscribe(c,start_date='2026-02-01').json()['id']
    path='/api/demo/abt/'+cid+'/validate'
    assert c.post(path,headers=auth(),json={'passage_id':'early','occurred_at':'2026-01-31T12:00:00Z'}).status_code==409
    bill(f);assert all(i['status']=='pending' for i in snapshot(c)['invoices'])
    advance(mp,'2026-02-01T16:00:00Z');bill(f)
    assert c.post(path,headers=auth(),json={'passage_id':'valid','occurred_at':'2026-02-01T00:00:00Z'}).status_code==200
