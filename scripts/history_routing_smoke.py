"""Read-only routing/history checks against real services; fixture inference is explicit."""
import argparse
import json
from pathlib import Path
import time
import uuid
import httpx
from maas.organizations import sign_scope
from maas.security import USERS

parser = argparse.ArgumentParser()
parser.add_argument('--live', action='store_true')
parser.add_argument('--proof-order')
args = parser.parse_args()
base = 'http://api:8000'
evidence = {'mode': 'live' if args.live else 'fixture', 'checks': []}
with httpx.Client(timeout=610) as client:
    def auth(uid, traveler=None):
        return {'Authorization': 'Bearer ' + client.post(base+'/api/demo/login/'+uid).json()['access_token'], 'X-MaaS-Coordination': sign_scope('maas-coordination', USERS[uid], traveler=traveler or (uid if uid in ('lea','adult') else None))}
    lea, clerk, alex = auth('lea'), auth('clerk','lea'), auth('adult')
    def get(path, headers, status=200):
        r=client.get(base+path,headers=headers)
        assert r.status_code==status,(path,r.status_code,r.text)
        return r.json()
    orders=get('/api/orders',lea)
    before={o['id']:o['state'] for o in orders}
    history=get('/api/assistant/purchases?limit=1',lea)
    assert history['total']==len(orders) and len(history['purchases'])==1 and history['has_more']
    assert get('/api/assistant/purchases?limit=1',clerk)['total']==len(orders)
    get('/api/assistant/purchases?traveler_id=lea',alex,403)
    evidence['checks'].append('history_pagination_and_traveler_isolation')
    selected=next(o for o in orders if {l['product'] for l in o['quote']['lines']}=={'transport','parking','bike'})
    r=client.post(base+'/api/chat',headers=lea,json={'message':'Quelle commission ?', 'order_id':selected['id']})
    r.raise_for_status();data=r.json()
    assert data['mode']=='clarification_required' and not data['inference'] and not data['evidence']['a2a_agents']
    evidence['checks'].append('ambiguous_scope_has_no_inference_or_delegation')
    questions=[('Quelle commission pour le parking ?', 'clearing', {'clearing','parking'},selected['id']),('Quels sont mes achats ?', 'history', {'history'}, None)]
    if args.proof_order:
        questions.append(('Vérifie les preuves blockchain de cette commande', 'verification', {'history'}, args.proof_order))
    evidence['cases']=[]
    for question,target,expected,oid in questions:
        if args.live:
            r=client.post(base+'/api/chat',headers=lea,json={'message':question,'order_id':oid})
            r.raise_for_status();data=r.json();agents=set(data['evidence']['a2a_agents']);tools=data['evidence']['mcp_tools'];text=data['text']
        else:
            context=sign_scope('maas-coordination', USERS['lea'],traveler='lea',order_id=oid,providers=['transport','parking','bike'] if oid else [])
            rid=uuid.uuid4().hex
            r=client.post('http://agent-fixture:8002/a2a/agents/conversation/v1/message:send',headers={**lea,'X-MaaS-Coordination':context},json={'jsonrpc':'2.0','id':rid,'method':'message/send','params':{'message':{'messageId':rid,'role':'user','parts':[{'kind':'text','text':question}]}}})
            r.raise_for_status();data=r.json();assert data['result']['status']['state']=='completed',data
            agents=set(filter(None,r.headers.get('X-MaaS-A2A-Agents','').split(',')));tools=r.headers.get('X-MaaS-MCP-Tools','').split(',');text=str(data)
        assert agents==expected,(question,agents,text)
        required_tool = 'verify_purchase_proofs' if target=='verification' else 'list_purchases' if target=='history' else 'read_provider_context'
        assert required_tool in tools,(question,tools,text)
        evidence['cases'].append({'question':question,'agents':sorted(agents),'tools':tools,'answer':text})
    if args.proof_order:
        for _ in range(30):
            proof=get('/api/assistant/purchases/'+args.proof_order+'/proofs',lea)
            if proof['status']=='verified':break
            time.sleep(1)
        assert proof['status']=='verified',proof
        assert {p['stage'] for p in proof['proofs']}=={'purchase','payment','delivery','usage','regularization'},proof
        get('/api/assistant/purchases/'+args.proof_order+'/proofs',alex,403)
        evidence['proof_verification']=proof
    assert before=={o['id']:o['state'] for o in get('/api/orders',lea)},'Read-only consultations changed orders'
evidence['status']='passed'
path=Path('/evidence/history-routing-'+evidence['mode']+'.json')
path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
print(json.dumps({'status':'passed','mode':evidence['mode'],'checks':evidence['checks'],'cases':[{'question':c['question'],'agents':c['agents'],'tools':c['tools']} for c in evidence['cases']],'proof_status':evidence.get('proof_verification',{}).get('status'),'evidence':str(path)},ensure_ascii=False))
