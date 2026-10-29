"""Local account rights and billing integration, including concurrent validator deliveries."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import time
import httpx
from maas.organizations import sign_scope
from maas.security import USERS
base='http://api:8000'
headers={u:{'Authorization':'Bearer '+httpx.post(base+'/api/demo/login/'+u).json()['access_token']} for u in ('lea','adult','clerk')}
on=datetime.now(timezone.utc).date().isoformat()
def post(path,body,uid='lea'):
    r=httpx.post(base+path,json=body,headers=headers[uid],timeout=30);r.raise_for_status();return r.json()
def account(uid):
    r=httpx.get(base+'/api/abt',headers=headers[uid]);r.raise_for_status();return r.json()
annual=post('/api/abt/subscriptions',{'traveler':'lea','product':'transport_annual','start_date':on,'consent':True,'idempotency_key':'abt-smoke-annual-'+on})
assert len(account('lea')['invoices'])==12
for uid in ('lea','adult'):
    current=account(uid)
    assert all(o['account_id']==current['id'] for o in current['orders']), 'Known purchase missing ABT account link'

postpaid=post('/api/abt/subscriptions',{'traveler':'adult','product':'transport_postpaid','start_date':on,'consent':True,'idempotency_key':'abt-smoke-postpaid-'+on},'adult')
existing=account('adult')['usages'];at=existing[0]['occurred_at'] if existing else datetime.now(timezone.utc).isoformat()
def validate(i):
    return post('/api/demo/abt/'+postpaid['id']+'/validate',{'passage_id':'smoke-'+str(i//2),'occurred_at':at},'adult')
with ThreadPoolExecutor(8) as pool: results=list(pool.map(validate,range(70)))
assert sum(not r['duplicate'] for r in results) in (0,35)
usages=account('adult')['usages'];assert len(usages)==35 and sum(u['charge_cents'] for u in usages)==6000
assert httpx.get(base+'/api/abt?traveler=lea',headers=headers['adult']).status_code==403
for _ in range(15):
    invoices=account('lea')['invoices']
    if any(i['status']=='paid_simulated' for i in invoices):break
    time.sleep(1)
assert sum(i['status']=='paid_simulated' for i in invoices)==1
assert not account('adult')['invoices'], 'Current-month usages must not be billed early'
# Read-only account tool over the A2A/MCP boundary, with fixture model explicitly simulated.
rid='abt-read-smoke';ctx=sign_scope('maas-coordination',USERS['lea'],traveler='lea')
r=httpx.post('http://agent-fixture:8002/a2a/agents/conversation/v1/message:send',headers={**headers['lea'],'X-MaaS-Coordination':ctx},json={'jsonrpc':'2.0','id':rid,'method':'message/send','params':{'message':{'messageId':rid,'role':'user','parts':[{'kind':'text','text':'Quelles sont les mensualités de mon compte mobilité ?'}]}}},timeout=60)
r.raise_for_status();assert r.json()['result']['status']['state']=='completed',r.text
assert 'read_abt_account' in r.headers.get('X-MaaS-MCP-Tools',''),r.text
print(json.dumps({'status':'passed','model':'fixture, no inference','annual_installments':12,'annual_total_cents':sum(i['amount_cents'] for i in invoices),'paid_installments':1,'postpaid_rides':35,'postpaid_cents':6000,'concurrent_deliveries':70,'cross_traveler_access':'denied','mcp':r.headers.get('X-MaaS-MCP-Tools')},ensure_ascii=False))
