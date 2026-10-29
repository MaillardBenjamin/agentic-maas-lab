import { useEffect, useRef, useState } from 'react';
type Data = Record<string, any>;
const money = (n: number) => (n / 100).toLocaleString('fr-FR', {style:'currency', currency:'EUR'});
const localDate = () => new Date().toLocaleDateString('en-CA');
export function AbtAccount({api, traveler}: {api: (path: string, method?: string, body?: any) => Promise<any>; traveler: string}) {
  const [data,setData]=useState<Data|null>(null), [error,setError]=useState(''), [busy,setBusy]=useState(false), [consent,setConsent]=useState(false), [product,setProduct]=useState('transport_annual'), [start,setStart]=useState(localDate);
  const pending=useRef<{key:string; body:Data}|null>(null);
  const live=useRef(true);
  const load=async()=>{const value=await api('/abt?traveler='+encodeURIComponent(traveler));if(live.current)setData(value);};
  useEffect(()=>{live.current=true;load().catch(e=>{if(live.current)setError(e.message);});return()=>{live.current=false;};},[traveler]);
  const run=async(fn:()=>Promise<void>)=>{setBusy(true);setError('');try{await fn();await load();}catch(e){if(live.current)setError((e as Error).message);}finally{if(live.current)setBusy(false);}};
  const subscribe=async()=>{
    if(!pending.current)pending.current={key:crypto.randomUUID(),body:{traveler,product,start_date:start,consent:true}};
    try {await api('/abt/subscriptions','POST',{...pending.current.body,idempotency_key:pending.current.key});pending.current=null;setConsent(false);} catch(e) {const status=(e as {status?:number}).status;if(status && status>=400 && status<500)pending.current=null;throw e;}
  };
  return <section className="card" aria-label="Compte mobilité ABT"><h2>Mon compte mobilité</h2><p>Vos droits transport restent sur votre compte. Prélèvements simulés, sans débit bancaire.</p>{error&&<p role="alert" className="alert error">{error}</p>}
    {data&&<><div className="traveler-products">{data.offers.map((p:Data)=><article key={p.id}><h3>{p.name}</h3><p>{p.billing==='annual_monthly'?`${money(p.annual_cents)} par an · 12 mensualités de ${money(p.monthly_cents)}. Trajets inclus.`:`${money(p.ride_cents)} par trajet · plafond de ${money(p.monthly_cap_cents)} par mois. Facturé le mois suivant.`}</p></article>)}</div>
    <label>Titre à souscrire<select value={product} disabled={busy||!!pending.current} onChange={e=>{setProduct(e.target.value);setConsent(false);}}>{data.offers.map((p:Data)=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
    <label>Début de validité<input type="date" min={localDate()} value={start} disabled={busy||!!pending.current} onChange={e=>{setStart(e.target.value);setConsent(false);}}/></label>
    <p>Validité d’un an, sans renouvellement automatique. Un seul titre ABT transport par période ; les autres services MaaS restent disponibles séparément.</p>
    <label className="check"><input type="checkbox" checked={consent} disabled={busy||!!pending.current} onChange={e=>setConsent(e.target.checked)}/>J’accepte le tarif sélectionné, la durée et les prélèvements mensuels simulés.</label>
    <button className="traveler-primary" disabled={busy||(!pending.current&&(!consent||!start))} onClick={()=>run(subscribe)}>{pending.current?'Retrouver ma souscription':'Confirmer ma souscription'}</button>
    <h3>Achats rattachés à mon compte</h3><p>{data.orders.length} commande(s) associée(s) à votre profil, y compris les achats sur le site et la borne. Leur suivi reste disponible dans Mes titres.</p>{data.orders.slice(-5).reverse().map((o:Data)=><div className="price-line" key={o.id}><span>{o.products.join(' + ')} · {o.created_at.slice(0,10)}</span><b>{money(o.total_cents)}</b></div>)}
    {data.contracts.map((c:Data)=><article className="card" key={c.id}><h3>{c.terms.name}</h3><p>Du {c.start_date} au {c.end_date} (fin exclue) · {c.status==='suspended'?'Suspendu : paiement à régulariser':c.status==='expired'?'Expiré':c.start_date>localDate()?'À venir':'Actif'}</p><p className="small">Référence : {c.id}</p><button className="traveler-secondary" disabled={busy||c.status!=='active'||c.start_date>localDate()} onClick={()=>run(async()=>{await api('/demo/abt/'+c.id+'/validate','POST',{passage_id:crypto.randomUUID(),occurred_at:new Date().toISOString()});})}>Simuler un trajet</button>
    <p>{data.usages.filter((u:Data)=>u.contract_id===c.id).length} trajet(s) enregistré(s) · montant après usage : {money(data.usages.filter((u:Data)=>u.contract_id===c.id).reduce((n:number,u:Data)=>n+u.charge_cents,0))}</p>
    <h4>Échéances et factures</h4>{data.invoices.filter((i:Data)=>i.contract_id===c.id).map((i:Data)=><div className="price-line" key={i.id}><span>{i.due_date} · {money(i.amount_cents)} · {i.status==='paid_simulated'?'Prélèvement simulé effectué':i.status==='failed'?'Échec à régulariser':'À prélever'}</span>{i.status==='failed'&&<button disabled={busy} onClick={()=>run(async()=>{await api('/demo/abt/invoices/'+i.id+'/collect','POST',{failed:false});})}>Régulariser (simulation)</button>}</div>)}
    {c.terms.billing==='postpaid'&&<p>Les usages du mois en cours seront facturés le mois suivant. Un trajet accepté ne signifie pas un paiement encaissé.</p>}</article>)}
    <button className="traveler-link" disabled={busy} onClick={()=>run(async()=>{})}>Actualiser mon compte</button></>}
  </section>;
}
