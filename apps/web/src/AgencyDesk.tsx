import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Building2, Check, CheckCircle2, ClipboardList, Headphones, History, LogOut, MessageSquare, Plus, RefreshCw, Search, ShieldCheck, ShoppingBag, Ticket, UserRound } from 'lucide-react';
import { Assistant } from './Assistant';
import { AgentActivity } from './AgentActivity';
import { DemoScope, type AIProvider } from './DemoScope';
import { agencyQuoteMatches, euroCents, matchingCustomers, preferredAgencyOrder, regularizationAllowed } from './agency-state';
import { bridgePaymentUrl } from './kiosk-state';
import { deliveryConfirmed, localTravelDate } from './traveler-state';
import './agency.css';

type Data = Record<string, any>;
type Tab = 'orders' | 'contact' | 'sale';
const money = (cents: number) => new Intl.NumberFormat('fr-FR', {style: 'currency', currency: 'EUR'}).format(cents / 100);
const date = (value: string) => new Intl.DateTimeFormat('fr-FR', {dateStyle: 'short', timeStyle: 'short'}).format(new Date(value));
const statuses: Data = {open: 'À traiter', pending: 'En attente', resolved: 'Résolu'};
const orderStates: Data = {payment_pending: 'À régler', paid: 'Paiement reçu', issuance_pending: 'Chargement en cours', awaiting_resume: 'Chargement suspendu', fulfilled: 'Délivré', reconciliation_required: 'À vérifier', failed: 'Interrompu'};
const motives: Data = {information: 'Information et tarifs', sale: 'Vente accompagnée', payment: 'Paiement', delivery: 'Titre ou chargement', parking: 'Parking relais', bike: 'Vélo partagé', other: 'Autre demande'};
const channels: Data = {station: 'Accueil en gare', phone: 'Téléphone', email: 'Courriel'};
const names: Data = {clerk: 'Camille', supervisor: 'Sam'};
class RequestError extends Error { constructor(public detail: any, public status: number) { super(typeof detail === 'string' ? detail : detail?.message || 'La demande n’a pas abouti.'); } }
class OldSession extends Error {}

export function AgencyDesk() {
  const [operator, setOperator] = useState('clerk'), [workplace, setWorkplace] = useState('station');
  const [session, setSession] = useState<Data | null>(null), [auth, setAuth] = useState('');
  const [customers, setCustomers] = useState<Data[]>([]), [orders, setOrders] = useState<Data[]>([]), [cases, setCases] = useState<Data[]>([]);
  const [catalog, setCatalog] = useState<Data | null>(null), [integrations, setIntegrations] = useState<Data[]>([]);
  const [query, setQuery] = useState(''), [customerId, setCustomerId] = useState(''), [orderId, setOrderId] = useState(''), [caseId, setCaseId] = useState('');
  const [details, setDetails] = useState<Data | null>(null), [statement, setStatement] = useState<Data | null>(null), [contact, setContact] = useState<Data | null>(null);
  const [tab, setTab] = useState<Tab>('orders'), [queue, setQueue] = useState('active');
  const [drafts, setDrafts] = useState<Record<string, Data>>({}), [notes, setNotes] = useState<Record<string, string>>({});
  const [amount, setAmount] = useState('2,00'), [reason, setReason] = useState(''), [confirmed, setConfirmed] = useState(false), [receipt, setReceipt] = useState<Data | null>(null);
  const [products, setProducts] = useState<string[]>(['transport']), [travelDate, setTravelDate] = useState(localTravelDate), [quote, setQuote] = useState<Data | null>(null), [saleConsent, setSaleConsent] = useState(false), [paymentMode, setPaymentMode] = useState('local_simulator'), [paymentConsent, setPaymentConsent] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState(''), [syncError, setSyncError] = useState('');
  const epoch = useRef(0), focus = useRef(0), lock = useRef(false);
  const attempts = useRef(new Map<string, Data>());
  const contactGeneration = useRef(0);
  const workspace = useRef<HTMLDivElement>(null);
  const customer = customers.find(value => value.id === customerId);
  const clientOrders = orders.filter(value => value.traveler === customerId);
  const currentOrder = clientOrders.find(value => value.id === orderId);
  const order = details?.id === orderId && details?.traveler === customerId ? details : currentOrder || null;
  const delivered = !!order && deliveryConfirmed({state: order.state, payment_count: order.payment_count, card: order.card});
  const currentCase = contact?.id === caseId && contact?.traveler === customerId ? contact : null;
  const draft = drafts[customerId] || {channel: workplace === 'station' ? 'station' : 'phone', motive: 'information', summary: ''};
  const provider: AIProvider = integrations.some(i => i.name === 'Ollama' && i.mode === 'configured') ? 'ollama' : integrations.some(i => i.name === 'OpenAI' && i.mode === 'configured') ? 'openai' : 'disabled';
  const bridgeEnabled = integrations.some(i => i.name === 'Bridge' && i.mode === 'configured');
  const visibleCustomers = matchingCustomers(customers, orders, query);
  const queueCases = cases.filter(value => queue === 'all' || (queue === 'active' ? value.status !== 'resolved' : value.status === 'resolved'));

  useEffect(() => () => { epoch.current++; focus.current++; }, []);
  useEffect(() => { if (session) window.scrollTo({top: 0, behavior: 'instant'}); }, [!!session]);
  useEffect(() => { if (customerId && window.innerWidth <= 1000) workspace.current?.scrollIntoView({block: 'start', behavior: 'instant'}); }, [customerId, caseId]);
  async function api(path: string, method = 'GET', body?: Data | Blob, bearer = auth) {
    const version = epoch.current;
    let response: Response;
    try {
      response = await fetch('/api' + path, {method, headers: {'Content-Type': body instanceof Blob ? body.type || 'application/octet-stream' : 'application/json', ...(body instanceof Blob ? {'X-Capture-Consent': 'true'} : {}), ...(bearer ? {Authorization: 'Bearer ' + bearer} : {})}, body: body instanceof Blob ? body : body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(path === '/chat' ? 610000 : 20000)});
    } catch { if (version !== epoch.current) throw new OldSession(); throw new Error('Service indisponible. Actualisez le dossier avant de renouveler une opération.'); }
    const value = await response.json().catch(() => ({}));
    if (version !== epoch.current) throw new OldSession();
    if (response.status === 401) { closeSession(); throw new Error('Session expirée. Reprenez votre poste pour consulter les opérations conservées.'); }
    if (!response.ok) throw new RequestError(value.detail || 'Opération indisponible.', response.status);
    return value;
  }
  function closeSession() {
    epoch.current++; focus.current++; setAuth(''); setSession(null); setCustomers([]); setOrders([]); setCases([]); setDetails(null); setContact(null); setStatement(null); setCustomerId(''); setOrderId(''); setCaseId(''); setDrafts({}); setNotes({}); setQuote(null); setReason(''); setReceipt(null); setConfirmed(false); setError(''); setNotice(''); setSyncError(''); attempts.current.clear();
  }
  async function login() {
    setBusy(true); setError('');
    try { const value = await api('/demo/login/' + operator, 'POST', undefined, ''); setAuth(value.access_token); setSession(value.user); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function refresh() {
    const version = epoch.current;
    const [o, c, u, cat, i] = await Promise.all([api('/orders'), api('/agency/cases'), api('/demo/users'), api('/catalog'), api('/integrations')]);
    if (version !== epoch.current) return;
    setOrders(o); setCases(c); setCustomers(u.filter((value: Data) => value.role === 'traveler' && value.org === session?.org)); setCatalog(cat); setIntegrations(i); setSyncError('');
  }
  useEffect(() => {
    if (!auth) return;
    let live = true;
    const update = () => refresh().catch(e => { if (live && !(e instanceof OldSession)) setSyncError(e.message); });
    update(); const timer = setInterval(update, 4000);
    return () => { live = false; clearInterval(timer); };
  }, [auth]);
  async function refreshDetails() {
    const version = focus.current;
    const [o, s, c] = await Promise.all([orderId ? api('/orders/' + orderId) : null, orderId ? api('/orders/' + orderId + '/statement') : null, caseId ? api('/agency/cases/' + caseId) : null]);
    if (version !== focus.current) return;
    setDetails(o); setStatement(s); setContact(previous => c && previous && previous.id === c.id && previous.revision > c.revision ? previous : c);
  }
  useEffect(() => {
    if (!auth) return;
    let live = true;
    const update = () => refreshDetails().catch(e => { if (live && !(e instanceof OldSession)) setSyncError(e.message); });
    update(); const timer = setInterval(update, 4000);
    return () => { live = false; clearInterval(timer); };
  }, [auth, customerId, orderId, caseId]);
  async function mutate(fn: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(''); setNotice(''); const version = epoch.current;
    try { await fn(); if (version === epoch.current) await refresh(); }
    catch (e) { if (version === epoch.current && !(e instanceof OldSession)) setError((e as Error).message); }
    finally { lock.current = false; if (version === epoch.current) setBusy(false); }
  }
  function chooseCustomer(id: string, linkedOrder?: string, linkedCase = '') {
    focus.current++; setCustomerId(id); setOrderId(linkedOrder ?? preferredAgencyOrder(orders, id, query)); setCaseId(linkedCase); setDetails(null); setStatement(null); setContact(null); setQuote(null); setSaleConsent(false); setConfirmed(false); setPaymentConsent(false); setReceipt(null); setReason(''); setError(''); setNotice(''); setTab(linkedCase ? 'contact' : 'orders');
  }
  function chooseOrder(id: string) {
    focus.current++; setOrderId(id); setDetails(null); setStatement(null); setReceipt(null); setConfirmed(false); setPaymentConsent(false); setReason(''); setError(''); setNotice('');
  }
  function editDraft(key: string, value: string) { setDrafts(previous => ({...previous, [customerId]: {...draft, [key]: value}})); }
  function intent(key: string, body: Data) {
    if (!attempts.current.has(key)) attempts.current.set(key, {...body, idempotency_key: 'agency-' + crypto.randomUUID()});
    return attempts.current.get(key)!;
  }
  async function createContact() {
    await mutate(async () => {
      const body = {traveler: customerId, order_id: orderId || null, ...draft};
      const key = 'contact:' + contactGeneration.current + ':' + JSON.stringify(body);
      const value = await api('/agency/cases', 'POST', intent(key, body));
      focus.current++; setCaseId(value.id); setContact(value); setTab('contact'); setDrafts(previous => ({...previous, [customerId]: {...draft, summary: ''}}));
      setNotice('Dossier ouvert et affecté à ' + names[session!.id] + '.');
    });
  }
  async function updateContact(status?: string) {
    if (!currentCase) return;
    const note = notes[caseId] || '';
    const key = 'update:' + caseId + ':' + note + ':' + status;
    await mutate(async () => {
      try {
        const value = await api('/agency/cases/' + caseId + '/updates', 'POST', intent(key, {revision: currentCase.revision, note, ...(status ? {status} : {})}));
        attempts.current.delete(key); setContact(value); setNotes(previous => ({...previous, [caseId]: ''})); setNotice('Dossier mis à jour.');
      } catch (e) { if (e instanceof RequestError && e.status === 409) { attempts.current.delete(key); await refreshDetails(); } throw e; }
    });
  }
  async function regularize() {
    const cents = euroCents(amount);
    if (!regularizationAllowed(order, cents, session!.role) || reason.trim().length < 5 || !confirmed) return;
    await mutate(async () => {
      const value = await api('/orders/' + orderId + '/refunds', 'POST', intent('refund:' + orderId + ':' + cents + ':' + reason.trim(), {amount_cents: cents, reason: reason.trim()}));
      setReceipt(value); setConfirmed(false); await refreshDetails(); setNotice('Régularisation comptable simulée enregistrée.');
    });
  }
  function changeSale(nextProducts = products, nextDate = travelDate) { setProducts(nextProducts); setTravelDate(nextDate); setQuote(null); setSaleConsent(false); }
  async function prepareSale() { await mutate(async () => { setQuote(await api('/quotes', 'POST', {traveler: customerId, seller: 'agency', products, travel_date: travelDate})); setSaleConsent(false); }); }
  async function confirmSale() {
    if (!agencyQuoteMatches(quote, customerId, products, travelDate) || !saleConsent) return;
    await mutate(async () => {
      try {
        const value = await api('/orders', 'POST', intent('sale:' + quote!.id + ':' + paymentMode, {quote_id: quote!.id, channel: 'agency', payment_mode: paymentMode, pause_before_issue: false}));
        chooseOrder(value.id); setTab('orders'); setQuote(null); setSaleConsent(false); setNotice('Commande créée. Vérifiez le règlement avant délivrance.');
      } catch (e) { if (e instanceof RequestError && e.detail?.order_id) { chooseOrder(e.detail.order_id); setTab('orders'); } throw e; }
    });
  }

  if (!session) return <div className="agency-login agency-desk"><p className="agency-kicker">ALIZÉ · RELATION VOYAGEURS</p><div className="agency-login-grid"><div><h1>Votre poste<br />conseiller.</h1><p>Accueillir, vendre et résoudre une demande, en gare comme en centre de relation client.</p><span className="agency-demo">Démonstration · identités et opérations fictives</span></div><section className="agency-card"><h2>Prendre mon poste</h2><label>Environnement de travail<select value={workplace} disabled={busy} onChange={e => setWorkplace(e.target.value)}><option value="station">Agence en gare</option><option value="crc">Centre de relation client · CRC</option></select></label><label>Profil de démonstration<select value={operator} disabled={busy} onChange={e => setOperator(e.target.value)}><option value="clerk">Camille · conseiller</option><option value="supervisor">Sam · superviseur</option></select></label><p className="agency-muted">{operator === 'clerk' ? 'Délégation de régularisation : 5 € par opération.' : 'Profil superviseur : contrôle des opérations au-delà de 5 €.'}</p><button className="agency-primary" disabled={busy} onClick={login}>Ouvrir le poste <ArrowRight size={17} /></button>{error && <p role="alert" className="alert error">{error}</p>}</section></div></div>;

  return <div className="agency-desk">
    <div className="agency-top"><div><span className="agency-kicker">ALIZÉ · RELATION VOYAGEURS</span><h1>{workplace === 'station' ? <Building2 size={24} /> : <Headphones size={24} />}{workplace === 'station' ? 'Poste agence en gare' : 'Centre de relation client'}</h1></div><div className="agency-session"><span><i />{names[session.id]} · {session.role === 'clerk' ? 'Conseiller' : 'Superviseur'}</span><button disabled={busy} aria-label="Actualiser le poste" onClick={() => mutate(async () => { await refreshDetails(); })}><RefreshCw size={16} /></button><button disabled={busy} onClick={closeSession}><LogOut size={15} />Fin de poste</button></div></div>
    <div className="agency-context"><span className="agency-demo">Mode démonstration · aucun argent réel</span><span>{workplace === 'station' ? 'Accueil physique · lecteur de carte et terminal non raccordés' : 'Contacts téléphone et courriel · téléphonie et messagerie non raccordées'}</span><label>Poste<select value={workplace} disabled={busy} onChange={e => setWorkplace(e.target.value)}><option value="station">En gare</option><option value="crc">CRC</option></select></label></div>
    {(error || syncError) && <p role="alert" className="alert error">{error || syncError}</p>}{notice && <p role="status" className="alert success"><Check size={16} />{notice}</p>}
    <div className="agency-layout">
      <div className="agency-sidebar">
        <section className="agency-card"><h2><Search size={17} />Retrouver un voyageur</h2><label className="agency-search"><span>Nom, identifiant ou référence de commande</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Ex. Léa, Alex ou référence…" /></label><div className="agency-client-list">{visibleCustomers.map(value => <button key={value.id} disabled={busy} className={customerId === value.id ? 'selected' : ''} onClick={() => chooseCustomer(value.id)}><span className="agency-avatar">{value.id === 'lea' ? 'L' : 'A'}</span><span><strong>{value.id === 'lea' ? 'Léa' : 'Alex'}</strong><small>{value.student_verified ? 'Profil étudiant' : 'Profil adulte'} · fictif</small></span><ArrowRight size={15} /></button>)}{!visibleCustomers.length && <p className="agency-muted">{customers.length ? 'Aucun voyageur ne correspond à cette recherche.' : 'Chargement des profils…'}</p>}</div></section>
        <section className="agency-card"><h2><ClipboardList size={17} />Dossiers de contact</h2><label>Afficher<select value={queue} onChange={e => setQueue(e.target.value)}><option value="active">À traiter et en attente</option><option value="resolved">Résolus</option><option value="all">Tous les dossiers</option></select></label><p className="agency-muted">{queueCases.length} dossier(s) · équipe relation voyageurs</p><div className="agency-case-list">{queueCases.map(value => <button key={value.id} className={caseId === value.id ? 'selected' : ''} disabled={busy} onClick={() => chooseCustomer(value.traveler, value.order_id || '', value.id)}><span className="agency-case-top"><strong>{value.traveler === 'lea' ? 'Léa' : 'Alex'}</strong><span className={'agency-status ' + value.status}>{statuses[value.status]}</span></span><span>{motives[value.motive]}</span><small>{channels[value.channel]} · {date(value.updated_at)}</small></button>)}</div>{!queueCases.length && <p className="agency-empty">Aucun dossier dans cette vue. Sélectionnez un voyageur pour enregistrer sa demande.</p>}</section>
      </div>
      <div className="agency-workspace" ref={workspace}>
        {!customer ? <section className="agency-card agency-start"><UserRound size={40} /><h2>Commencez par le voyageur</h2><p>Recherchez son nom ou une référence de commande, puis consultez ses titres, préparez une vente ou ouvrez un dossier de contact.</p><div><span><Ticket size={18} />Commandes et titres</span><span><ShoppingBag size={18} />Vente accompagnée</span><span><MessageSquare size={18} />Suivi de la demande</span></div></section> : <>
          <section className="agency-card agency-customer"><span className="agency-avatar large">{customer.id === 'lea' ? 'L' : 'A'}</span><div><span className="agency-kicker">DOSSIER VOYAGEUR · {customer.id.toUpperCase()}</span><h2>{customer.id === 'lea' ? 'Léa' : 'Alex'} <span className="agency-status">Identité fictive</span></h2><p>{customer.student_verified ? 'Droit étudiant fictif enregistré · valable jusqu’au ' + new Date(customer.student_until + 'T12:00:00').toLocaleDateString('fr-FR') : 'Profil adulte · tarif standard'} · {clientOrders.length} commande(s)</p></div><button disabled={busy} onClick={() => { contactGeneration.current++; focus.current++; setCaseId(''); setContact(null); setTab('contact'); }}><Plus size={15} />Nouveau contact</button></section>
          <nav className="agency-tabs" aria-label="Actions du conseiller">{([['orders', 'Commandes et titres', Ticket], ['contact', 'Dossier de contact', ClipboardList], ['sale', 'Vente accompagnée', ShoppingBag]] as const).map(([key, title, Icon]) => <button key={key} className={tab === key ? 'active' : ''} disabled={busy} onClick={() => { if (key === 'contact' && currentCase) chooseOrder(currentCase.order_id || ''); setTab(key); setError(''); }}><Icon size={16} />{title}</button>)}</nav>
          {tab === 'orders' && <>
            <section className="agency-card"><h2>Commandes du voyageur</h2>{!clientOrders.length ? <p className="agency-empty">Aucune commande. Vous pouvez préparer une vente accompagnée.</p> : <><label>Commande<select value={orderId} disabled={busy} onChange={e => chooseOrder(e.target.value)}><option value="">Choisir une commande</option>{clientOrders.map(value => <option key={value.id} value={value.id}>{value.id.slice(-8)} · {money(value.quote.total_cents)} · {orderStates[value.state] || value.state}</option>)}</select></label>{order && <div className="agency-order"><div className="agency-order-heading"><span><strong>Commande {order.id.slice(-8)}</strong><small>{date(order.created_at)} · {{web: 'Site / application', automate: 'Automate', agency: 'Agence'}[order.channel as string] || order.channel}</small></span><span className={'agency-status ' + (delivered ? 'resolved' : 'pending')}>{orderStates[order.state] || order.state}</span></div><div className="agency-order-lines">{order.quote.lines.map((line: Data) => <div key={line.product}><span>{{transport: 'Transport Alizé', parking: 'Parking relais', bike: 'Accès vélo'}[line.product as string] || line.product}</span><strong>{line.product === 'bike' ? 'Après usage' : money(line.amount_cents)}</strong></div>)}</div><div className="agency-facts"><span>Prépayé<strong>{money(order.quote.total_cents)}</strong></span><span>Règlement<strong>{order.payment_count > 0 ? 'Reçu' : 'À recevoir'}</strong></span><span>Délivrance<strong>{delivered ? 'Relue sur carte stub' : 'À confirmer'}</strong></span><span>Régularisé<strong>{money(order.refund_cents)}</strong></span></div>
              {!order.payment_count && <div className="agency-payment"><h3>Règlement de démonstration</h3>{order.payment_mode === 'local_simulator' ? <><label className="agency-check"><input type="checkbox" checked={paymentConsent} disabled={busy} onChange={e => setPaymentConsent(e.target.checked)} />Je confirme le règlement simulé de {money(order.quote.total_cents)} pour cette commande.</label><button className="agency-primary" disabled={busy || !paymentConsent} onClick={() => mutate(async () => { await api('/demo/orders/' + order.id + '/pay', 'POST'); setPaymentConsent(false); await refreshDetails(); setNotice('Règlement simulé reçu. Le chargement est suivi automatiquement.'); })}>Enregistrer le règlement simulé</button></> : <><button disabled={busy} onClick={() => mutate(async () => { await api('/orders/' + order.id + '/bridge/payment', 'POST', {}); await refreshDetails(); })}>Préparer le lien Bridge sandbox</button>{bridgePaymentUrl(order.bridge?.url) && <a href={bridgePaymentUrl(order.bridge.url)!} target="_blank" rel="noreferrer">Ouvrir le paiement de démonstration ↗</a>}<button disabled={busy} onClick={() => mutate(async () => { await api('/orders/' + order.id + '/bridge/status', 'POST', {}); await refreshDetails(); })}>Vérifier le règlement</button></>}</div>}
              {order.state === 'awaiting_resume' && <button disabled={busy} onClick={() => mutate(async () => { await api('/demo/orders/' + order.id + '/continue', 'POST'); setNotice('Reprise du chargement demandée.'); })}>Reprendre le chargement suspendu</button>}
              {order.state === 'reconciliation_required' && <p className="alert error">Le chargement doit être vérifié. Ouvrez un dossier de contact pour tracer le suivi.</p>}
              {statement && statement.order_id === order.id && <p className="agency-muted">Net prépayé : {money(statement.net_prepaid_cents)} · Vélo à facturer : {money(statement.bike_due_cents)}{statement.parking_adjustment_available_cents > 0 && <> · Régularisation P+R à examiner : {money(statement.parking_adjustment_available_cents)}</>}</p>}
              <details className="agency-history"><summary><History size={15} />Historique des usages ({order.events?.length || 0})</summary>{order.events?.length ? order.events.map((event: Data) => <p key={event.id}>{date(event.time)} · {{'maas.validation.accepted.v1': 'Validation transport', 'maas.parking.ended.v1': 'Sortie parking', 'maas.bike.ended.v1': 'Restitution vélo'}[event.type as string] || event.type}</p>) : <p>Aucun usage enregistré sur cette commande.</p>}</details>
            </div>}</>}</section>
            {order && <section className="agency-card"><h2><ShieldCheck size={17} />Régulariser la commande</h2><p className="agency-muted">Délégation {session.role === 'clerk' ? 'conseiller : 5 €' : 'superviseur : 1 000 €'} maximum par opération, dans la limite du montant prépayé restant. L’autorisation est contrôlée côté serveur.</p>{receipt ? <div className="agency-receipt"><CheckCircle2 size={24} /><strong>{money(receipt.amount_cents)} régularisés</strong><p>{receipt.reason}</p><small>Reçu {receipt.id.slice(-10)} · {names[receipt.principal] || receipt.principal}</small><p>Aucun remboursement bancaire exécuté.</p><button onClick={() => { attempts.current.delete('refund:' + orderId + ':' + euroCents(amount) + ':' + reason.trim()); setReceipt(null); setConfirmed(false); setReason(''); }}>Nouvelle régularisation</button></div> : <><div className="agency-form-grid"><label>Montant à régulariser (€)<input inputMode="decimal" value={amount} disabled={busy} onChange={e => { setAmount(e.target.value); setConfirmed(false); }} /></label><label>Motif de la régularisation<input value={reason} maxLength={300} disabled={busy} onChange={e => { setReason(e.target.value); setConfirmed(false); }} placeholder="Ex. réduction P+R après validation" /></label></div><label className="agency-check"><input type="checkbox" checked={confirmed} disabled={busy} onChange={e => setConfirmed(e.target.checked)} />Je confirme le montant, le motif et la commande {order.id.slice(-8)}.</label><button className="agency-primary" disabled={busy || !confirmed || reason.trim().length < 5 || !regularizationAllowed(order, euroCents(amount), session.role)} onClick={regularize}>Confirmer la régularisation simulée</button>{euroCents(amount) !== null && !regularizationAllowed(order, euroCents(amount), session.role) && <p className="agency-warning">Montant hors délégation, supérieur au prépayé restant ou commande non réglée. {session.role === 'clerk' && euroCents(amount)! > 500 ? 'Le profil superviseur doit confirmer une opération au-delà de 5 €.' : ''}</p>}<p className="agency-muted">Écriture comptable de démonstration. Aucun remboursement bancaire.</p></>}</section>}
          </>}
          {tab === 'contact' && <section className="agency-card"><h2><MessageSquare size={18} />{currentCase ? 'Suivi du dossier ' + currentCase.id.slice(-8) : 'Ouvrir un dossier de contact'}</h2>{currentCase ? <><div className="agency-case-meta"><span className={'agency-status ' + currentCase.status}>{statuses[currentCase.status]}</span><span>{channels[currentCase.channel]} · {motives[currentCase.motive]}</span><span>Affecté à {names[currentCase.assigned_to] || currentCase.assigned_to}</span></div><p><strong>{currentCase.summary}</strong></p><p className="agency-muted">{currentCase.order_id ? 'Commande liée : ' + currentCase.order_id.slice(-8) : 'Demande sans commande liée'}</p><ol className="agency-notes">{currentCase.notes.map((entry: Data) => <li key={entry.id}><span>{names[entry.author] || entry.author} · {date(entry.at)} · {statuses[entry.status]}</span>{entry.text && <p>{entry.text}</p>}</li>)}</ol><label>Note de traitement ou réponse apportée<textarea rows={4} maxLength={2000} disabled={busy} value={notes[caseId] || ''} onChange={e => setNotes(previous => ({...previous, [caseId]: e.target.value}))} placeholder="Décrivez la vérification et la réponse apportée au voyageur." /></label><div className="agency-actions"><button disabled={busy || !(notes[caseId] || '').trim()} onClick={() => updateContact()}>Enregistrer la note</button>{currentCase.status !== 'resolved' ? <><button disabled={busy || currentCase.status === 'pending'} onClick={() => updateContact('pending')}>Mettre en attente</button><button className="agency-primary" disabled={busy || (notes[caseId] || '').trim().length < 5} onClick={() => updateContact('resolved')}>Clôturer avec la réponse</button></> : <button disabled={busy} onClick={() => updateContact('open')}>Rouvrir le dossier</button>}</div></> : <><p className="agency-muted">Enregistrez le motif et le canal du contact. Les notes restent dans le dossier relation client.</p><div className="agency-form-grid"><label>Canal de contact<select value={draft.channel} disabled={busy} onChange={e => editDraft('channel', e.target.value)}>{Object.entries(channels).map(([key, value]) => <option key={key} value={key}>{value as string}</option>)}</select></label><label>Motif<select value={draft.motive} disabled={busy} onChange={e => editDraft('motive', e.target.value)}>{Object.entries(motives).map(([key, value]) => <option key={key} value={key}>{value as string}</option>)}</select></label></div><label>Commande concernée<select value={orderId} disabled={busy} onChange={e => chooseOrder(e.target.value)}><option value="">Sans commande</option>{clientOrders.map(value => <option key={value.id} value={value.id}>{value.id.slice(-8)} · {money(value.quote.total_cents)}</option>)}</select></label><label>Demande du voyageur<textarea rows={4} maxLength={500} value={draft.summary} disabled={busy} onChange={e => editDraft('summary', e.target.value)} placeholder="Décrivez la demande de démonstration…" /></label><button className="agency-primary" disabled={busy || draft.summary.trim().length < 5} onClick={createContact}>Ouvrir et prendre en charge le dossier</button></>}</section>}
          {tab === 'sale' && <section className="agency-card"><h2><ShoppingBag size={18} />Vente accompagnée</h2><p className="agency-muted">Préparez le devis du voyageur. Le vendeur est Agence Alizé ; les réductions sont calculées sur le profil et la date d’utilisation.</p><label>Date d’utilisation<input type="date" value={travelDate} disabled={busy} onChange={e => changeSale(products, e.target.value)} /></label><fieldset className="agency-products"><legend>Produits à proposer</legend>{catalog?.products.map((product: Data) => <label key={product.id} className="agency-check"><input type="checkbox" checked={products.includes(product.id)} disabled={busy} onChange={() => changeSale(products.includes(product.id) ? products.filter(value => value !== product.id) : [...products, product.id])} /><span>{product.name}<small>{product.id === 'bike' ? 'Facturation après usage' : money(product.price_cents) + ' au tarif public'}</small></span></label>)}</fieldset><label>Règlement<select disabled={busy} value={paymentMode} onChange={e => { setPaymentMode(e.target.value); setSaleConsent(false); }}><option value="local_simulator">Règlement local simulé</option>{bridgeEnabled && <option value="bridge_sandbox">Lien de paiement Bridge sandbox</option>}</select></label><button disabled={busy || !products.length || !travelDate} onClick={prepareSale}>Calculer le devis</button>{quote && <div className="agency-quote"><h3>Devis de l’agence · {money(quote.total_cents)}</h3>{quote.lines.map((line: Data) => <p key={line.product}><span>{{transport: 'Transport', parking: 'Parking', bike: 'Vélo après usage'}[line.product as string] || line.product}</span><strong>{money(line.amount_cents)}</strong></p>)}<label className="agency-check"><input type="checkbox" checked={saleConsent} disabled={busy} onChange={e => setSaleConsent(e.target.checked)} />Le voyageur a validé les produits, la date et le montant de ce devis de démonstration.</label><button className="agency-primary" disabled={busy || !saleConsent || !agencyQuoteMatches(quote, customerId, products, travelDate)} onClick={confirmSale}>Créer la commande · {money(quote.total_cents)}</button></div>}</section>}
        </>}
      </div>
      <div className="agency-assistance"><section className="agency-card"><span className="agency-kicker">AIDE À LA RÉSOLUTION</span><h2>Le conseiller garde la main.</h2><p className="agency-muted">Consultez les règles et expliquez le dossier avec l’assistant. Chaque opération reste confirmée dans le poste.</p>{customer && <p className="agency-context-note">Contexte : {customer.id === 'lea' ? 'Léa' : 'Alex'}{orderId ? ' · commande ' + orderId.slice(-8) : ' · sans commande sélectionnée'}</p>}</section><Assistant key={session.id + ':' + customerId + ':' + orderId} api={api} agent="conversation" orderId={orderId || undefined} runtimeProvider={provider} advisor travelerId={customerId || undefined} seller="agency" travelDate={travelDate} onProposal={proposal => { if (busy || proposal.traveler !== customerId || proposal.seller !== "agency") return; changeSale(proposal.lines.map((line: Data) => line.product), proposal.travel_date); setQuote(proposal); setTab("sale"); }} /><details className="agency-scope"><summary>Périmètre et équipements du poste</summary><DemoScope provider={provider} bridgeEnabled={bridgeEnabled} /></details></div>
    </div>
    <AgentActivity key={session.id} api={api} />
  </div>;
}
