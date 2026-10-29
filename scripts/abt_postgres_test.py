"""Fresh isolated PostgreSQL schema each run: exercises locks, not replay-only concurrency."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import uuid
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy.orm import sessionmaker
from maas import abt
from maas.db import Base, Record, engine as source
from maas.security import USERS, token

schema='abt_test_'+uuid.uuid4().hex
with source.begin() as conn:conn.execute(CreateSchema(schema))
engine=create_engine(source.url,execution_options={'schema_translate_map':{None:schema}})
Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
app=FastAPI();abt.register(app)
headers={'Authorization':'Bearer '+token(USERS['lea'])}
clock=[datetime(2026,1,31,16,tzinfo=timezone.utc)]
checks=[]
def post(path,body):
    with TestClient(app) as client:return client.post(path,json=body,headers=headers)
def values(kind):
    with factory() as db:return [r.data for r in db.scalars(select(Record).where(Record.kind==kind))]
try:
    with patch.object(abt,'Session',factory),patch.object(abt,'utc_now',lambda:clock[0]):
        body={'traveler':'lea','product':'transport_postpaid','start_date':'2026-01-31','consent':True,'idempotency_key':'same-request-123'}
        with ThreadPoolExecutor(8) as pool:results=list(pool.map(lambda _:post('/api/abt/subscriptions',body),range(8)))
        assert all(r.status_code==200 for r in results),[(r.status_code,r.text) for r in results]
        assert len(values('abt_contract'))==len(values('abt_account'))==1
        cid=results[0].json()['id'];checks.append('eight_concurrent_identical_subscriptions_one_contract')
        # Competing products and actors share the account lock.
        with ThreadPoolExecutor(4) as pool:
            results=list(pool.map(lambda i:post('/api/abt/subscriptions',{**body,'product':'transport_annual','idempotency_key':'different-key-'+str(i)}),range(4)))
        assert all(r.status_code==409 for r in results) and len(values('abt_contract'))==1
        checks.append('competing_subscriptions_no_overlap')
        def ride(i):return post('/api/demo/abt/'+cid+'/validate',{'passage_id':str(i//2),'occurred_at':'2026-01-31T12:00:00Z'})
        with ThreadPoolExecutor(8) as pool:results=list(pool.map(ride,range(70)))
        assert all(r.status_code==200 for r in results)
        assert sum(not r.json()['duplicate'] for r in results)==35,'Each run must create 35 NEW passages'
        assert len(values('abt_usage'))==35 and sum(u['charge_cents'] for u in values('abt_usage'))==6000
        checks.append('seventy_concurrent_deliveries_thirty_five_new_usages_cap_6000')
        clock[0]=datetime(2026,2,1,16,tzinfo=timezone.utc)
        def billing(_):
            with factory.begin() as db:abt.billing(db)
        with ThreadPoolExecutor(4) as pool:list(pool.map(billing,range(4)))
        bills=values('abt_invoice')
        assert len(bills)==1 and bills[0]['amount_cents']==6000 and len(bills[0]['attempts'])==1
        checks.append('four_concurrent_month_closures_one_invoice_one_collection')
        # Reset only this isolated invoice to test competing explicit retries.
        with factory.begin() as db:
            row=db.get(Record,bills[0]['id']);row.data={**row.data,'status':'failed','attempts':[]}
        with ThreadPoolExecutor(8) as pool:
            results=list(pool.map(lambda _:post('/api/demo/abt/invoices/'+bills[0]['id']+'/collect',{}),range(8)))
        assert all(r.status_code==200 for r in results)
        assert len(values('abt_invoice')[0]['attempts'])==1
        checks.append('eight_concurrent_debit_retries_one_effect')
    print(json.dumps({'status':'passed','database':'PostgreSQL, isolated temporary schema','checks':checks}))
finally:
    engine.dispose()
    with source.begin() as conn:conn.execute(DropSchema(schema,cascade=True))
