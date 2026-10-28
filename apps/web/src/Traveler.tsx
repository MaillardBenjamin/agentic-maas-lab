import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Bike, CarFront, Check, CheckCircle2, CreditCard, Headphones, LoaderCircle, LogOut, Minus, Plus, ShoppingBag, ShoppingCart, Ticket, UserRound, Wind } from "lucide-react";
import { Assistant } from "./Assistant";
import { AgentActivity } from "./AgentActivity";
import { DemoScope, type AIProvider } from "./DemoScope";
import { PartnerPanel } from "./PartnerPanel";
import { bridgePaymentUrl, quoteExpired } from "./kiosk-state";
import { deliveryConfirmed, localTravelDate, quoteMatchesCart } from "./traveler-state";
import "./traveler.css";

type Data = Record<string, any>;
type Page = "shop" | "cart" | "checkout" | "tickets" | "services" | "help";
const money = (value: number) => new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(value / 100);
const dateLabel = (date: string) => new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium" }).format(new Date(date));
const profiles = [
  { id: "lea", name: "Léa", initials: "L", description: "Étudiante", detail: "Droit étudiant fictif valable jusqu’au 31 août 2027." },
  { id: "adult", name: "Alex", initials: "A", description: "Adulte", detail: "Profil fictif au tarif standard." },
];
const productInfo: Record<string, { title: string; description: string; Icon: typeof Ticket }> = {
  transport: { title: "Transport Alizé", description: "Votre titre de transport sur le réseau de démonstration.", Icon: Ticket },
  parking: { title: "Parking relais", description: "Une journée de stationnement pour compléter votre trajet.", Icon: CarFront },
  bike: { title: "Vélo partagé", description: "L’accès au service vélo, facturé après restitution.", Icon: Bike },
};
const orderLabels: Record<string, string> = { payment_pending: "À payer", paid: "Paiement reçu", awaiting_resume: "Chargement à reprendre", issuance_pending: "Chargement en cours", fulfilled: "Titres délivrés", reconciliation_required: "Vérification nécessaire", failed: "Opération interrompue" };
class OldSession extends Error {}
class RequestError extends Error {
  constructor(public detail: any, public status = 0) { super(typeof detail === "string" ? detail : detail?.message || "La demande n’a pas abouti."); }
}

export function Traveler() {
  const [profileChoice, setProfileChoice] = useState("lea");
  const [profile, setProfile] = useState<Data | null>(null);
  const [auth, setAuth] = useState("");
  const [catalog, setCatalog] = useState<Data | null>(null);
  const [integrations, setIntegrations] = useState<Data[]>([]);
  const [page, setPage] = useState<Page>("shop");
  const [products, setProducts] = useState<string[]>([]);
  const [travelDate, setTravelDate] = useState(localTravelDate);
  const [quote, setQuote] = useState<Data | null>(null);
  const [quoting, setQuoting] = useState(false);
  const [quoteAttempt, setQuoteAttempt] = useState(0);
  const [orders, setOrders] = useState<Data[]>([]);
  const [selected, setSelected] = useState("");
  const [serviceOrder, setServiceOrder] = useState("");
  const [paymentMode, setPaymentMode] = useState("local_simulator");
  const [consent, setConsent] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [syncError, setSyncError] = useState("");
  const [visibleOrders, setVisibleOrders] = useState(8);
  const [clock, setClock] = useState(Date.now());
  const epoch = useRef(0), lock = useRef(false), ordersRevision = useRef(0);
  const purchase = useRef<Data | null>(null);
  const confirmationRetries = useRef(new Map<string, Data>());
  const order = orders.find(value => value.id === selected);
  const usableOrders = orders.filter(value => deliveryConfirmed(value as any));
  const serviceOrders = usableOrders.filter(value => value.quote.lines.some((line: Data) => ["bike", "parking"].includes(line.product)));
  const activeService = serviceOrders.find(value => value.id === serviceOrder) || serviceOrders[0];
  const provider: AIProvider = integrations.some(i => i.name === "Ollama" && i.mode === "configured") ? "ollama" : integrations.some(i => i.name === "OpenAI" && i.mode === "configured") ? "openai" : "disabled";
  const bridgeEnabled = integrations.some(i => i.name === "Bridge" && i.mode === "configured");
  const currentQuote = quoteMatchesCart(quote as any, products, travelDate, profile?.id || "");
  const expired = quote ? quoteExpired(quote.expires_at, clock) : false;
  const name = profiles.find(value => value.id === profile?.id)?.name || "";

  useEffect(() => () => { epoch.current++; }, []);
  useEffect(() => {
    if (!quote) return;
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [quote?.id]);

  function disconnect(message = "Vous êtes déconnecté. Vos commandes sont conservées dans votre compte de démonstration.") {
    epoch.current++;
    setProfile(null); setAuth(""); setCatalog(null); setIntegrations([]); setOrders([]);
    setProducts([]); setTravelDate(localTravelDate()); setQuote(null); setQuoting(false);
    setSelected(""); setServiceOrder(""); setPage("shop"); setConsent(false); setUncertain(false);
    setPaymentMode("local_simulator"); setVisibleOrders(8); setBusy(false); setError(""); setSyncError(""); setInfo(message);
    purchase.current = null; confirmationRetries.current.clear();
  }
  async function api(path: string, method = "GET", body?: Data | Blob, bearer = auth) {
    const version = epoch.current;
    let response: Response;
    try {
      response = await fetch("/api" + path, { method, headers: { "Content-Type": body instanceof Blob ? (body.type || "application/octet-stream") : "application/json", ...(body instanceof Blob ? { "X-Capture-Consent": "true" } : {}), ...(bearer ? { Authorization: "Bearer " + bearer } : {}) }, body: body instanceof Blob ? body : body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(path === "/chat" ? 610000 : 20000) });
    } catch {
      if (epoch.current !== version) throw new OldSession();
      throw new RequestError("Le service n’a pas répondu. Vous pouvez réessayer ; vos commandes enregistrées sont conservées.");
    }
    const value = await response.json().catch(() => ({}));
    if (epoch.current !== version) throw new OldSession();
    if (response.status === 401) {
      disconnect("Votre session a expiré. Reconnectez-vous au même profil pour retrouver vos commandes.");
      throw new OldSession();
    }
    if (!response.ok) throw new RequestError(value.detail || "Service temporairement indisponible.", response.status);
    return value;
  }
  async function perform(fn: () => Promise<void>) {
    if (lock.current) return;
    const version = epoch.current;
    lock.current = true; setBusy(true); setError(""); setInfo("");
    try { await fn(); }
    catch (e) { if (version === epoch.current && !(e instanceof OldSession)) setError((e as Error).message); }
    finally { lock.current = false; if (version === epoch.current) setBusy(false); }
  }
  function navigate(next: Page) {
    setPage(next); setError(""); setInfo("");
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  async function signIn() {
    const session = await api("/demo/login/" + profileChoice, "POST", undefined, "");
    const [offers, saved, status] = await Promise.all([
      api("/catalog", "GET", undefined, session.access_token),
      api("/orders", "GET", undefined, session.access_token),
      api("/integrations", "GET", undefined, session.access_token),
    ]);
    setAuth(session.access_token); setProfile(session.user); setCatalog(offers); setOrders(saved); setIntegrations(status);
    setPage("shop"); setInfo("");
  }
  function updateBasket(next: string[], date = travelDate) {
    if (uncertain || busy) return;
    setProducts(next); setTravelDate(date); setQuote(null); setConsent(false); setError("");
    purchase.current = null;
  }

  useEffect(() => {
    if (!profile || !auth) return;
    let live = true;
    const version = epoch.current;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        if (!lock.current) {
          const revision = ordersRevision.current;
          const saved = await api("/orders");
          if (live && version === epoch.current && revision === ordersRevision.current && !lock.current) { setOrders(saved); setSyncError(""); }
        }
      } catch (e) {
        if (live && version === epoch.current && !(e instanceof OldSession)) setSyncError("Le suivi est momentanément indisponible. Vos commandes sont conservées.");
      }
      if (live && version === epoch.current) timer = setTimeout(refresh, 2500);
    }
    timer = setTimeout(refresh, 2500);
    return () => { live = false; clearTimeout(timer); };
  }, [auth]);

  useEffect(() => {
    if (page !== "cart" || !products.length || !profile || uncertain) return;
    let live = true;
    const version = epoch.current;
    setQuoting(true); setQuote(null); setConsent(false); setError("");
    const timer = setTimeout(async () => {
      try {
        const value = await api("/quotes", "POST", { traveler: profile.id, products, seller: "app", travel_date: travelDate });
        if (live && epoch.current === version) { setQuote(value); setClock(Date.now()); }
      } catch (e) {
        if (live && epoch.current === version && !(e instanceof OldSession)) setError((e as Error).message);
      } finally { if (live && epoch.current === version) setQuoting(false); }
    }, 250);
    return () => { live = false; clearTimeout(timer); };
  }, [page, products, travelDate, auth, quoteAttempt]);

  function rememberOrder(saved: Data) {
    ordersRevision.current++;
    setOrders(list => [saved, ...list.filter(value => value.id !== saved.id)]);
    setSelected(saved.id);
  }
  async function confirm() {
    if (!purchase.current) {
      if (!consent || !currentQuote || !quote || quoteExpired(quote.expires_at)) {
        setQuoteAttempt(value => value + 1);
        throw new RequestError("Le devis doit être recalculé. Vérifiez le nouveau prix avant de confirmer.");
      }
      purchase.current = { quote_id: quote.id, idempotency_key: "traveler-" + crypto.randomUUID(), channel: "web", pause_before_issue: false, payment_mode: quote.total_cents === 0 ? "local_simulator" : paymentMode };
    }
    setUncertain(true);
    let saved: Data;
    try { saved = await api("/orders", "POST", purchase.current); confirmationRetries.current.delete(saved.id); }
    catch (e) {
      if (e instanceof OldSession) throw e;
      if (e instanceof RequestError && e.detail?.order_id) {
        confirmationRetries.current.set(e.detail.order_id, { ...purchase.current });
        saved = await api("/orders/" + e.detail.order_id);
      }
      else {
        if (e instanceof RequestError && e.status >= 400 && e.status < 500) { purchase.current = null; setUncertain(false); }
        throw e;
      }
    }
    rememberOrder(saved); setProducts([]); setQuote(null); setConsent(false); setUncertain(false);
    purchase.current = null; navigate("checkout");
  }
  async function refreshOrder(id: string) { rememberOrder(await api("/orders/" + id)); }
  async function pay(saved: Data) {
    try { await api("/demo/orders/" + saved.id + "/pay", "POST", {}); }
    catch (e) {
      if (e instanceof OldSession) throw e;
      const stored = await api("/orders/" + saved.id);
      rememberOrder(stored);
      if (!stored.payment_count) throw e;
      setInfo("Paiement de test enregistré. Le suivi du chargement peut être repris sans second paiement.");
      return;
    }
    await refreshOrder(saved.id);
  }
  async function resume(saved: Data) {
    const retry = confirmationRetries.current.get(saved.id);
    if (retry) {
      await api("/orders", "POST", retry);
      confirmationRetries.current.delete(saved.id);
      await refreshOrder(saved.id);
      return;
    }
    if (saved.state === "awaiting_resume") await api("/demo/orders/" + saved.id + "/continue", "POST", {});
    else if (saved.payment_mode === "local_simulator") await pay(saved);
    else await api("/orders/" + saved.id + "/bridge/status", "POST", {});
    await refreshOrder(saved.id);
  }
  const messages = <>{error && <p role="alert" className="alert error">{error}</p>}{info && <p role="status" className="alert success">{info}</p>}{syncError && <p role="status" className="alert error">{syncError}</p>}</>;

  function orderDetail(saved: Data) {
    const done = deliveryConfirmed(saved as any);
    const bank = saved.payment_mode === "bridge_sandbox";
    const bankUrl = bridgePaymentUrl(saved.bridge?.url);
    const confirmationPending = confirmationRetries.current.has(saved.id);
    return <section className="card traveler-checkout" aria-label="Suivi de la commande">
      <div className="traveler-checkout-title">{done ? <CheckCircle2 size={32} /> : saved.payment_count > 0 ? <LoaderCircle className="traveler-spin" size={32} /> : <CreditCard size={32} />}<div><h2>{done ? "Vos titres sont disponibles" : saved.state === "reconciliation_required" ? "Votre commande nécessite une vérification" : saved.payment_count > 0 ? "Nous préparons vos titres" : "Votre commande est enregistrée"}</h2><p>{done ? "Le chargement de votre carte de démonstration est confirmé." : saved.payment_count > 0 ? "Le paiement est enregistré. Aucun second paiement n’est nécessaire." : "Retrouvez ci-dessous le récapitulatif et la prochaine étape."}</p></div></div>
      <p className="traveler-order-ref">Commande {saved.id.slice(-12)} · {dateLabel(saved.created_at)}</p>
      <ol className="traveler-progress" aria-label="Progression de la commande"><li className="complete"><Check size={14} /> Commande</li><li className={saved.payment_count > 0 ? "complete" : "current"}>Paiement</li><li className={done ? "complete" : saved.payment_count > 0 ? "current" : ""}>Mes titres</li></ol>
      {saved.quote.lines.map((line: Data) => <div className="price-line" key={line.product}><span>{productInfo[line.product]?.title || line.name}</span><b>{line.product === "bike" ? "Après usage" : money(line.amount_cents)}</b></div>)}
      <div className="total"><span>{saved.payment_count ? "Montant confirmé" : "À payer maintenant"}</span><strong>{money(saved.quote.total_cents)}</strong></div>
      {confirmationPending && <div role="status" className="traveler-note"><p>Votre commande est enregistrée. Son traitement doit être relancé avant le paiement.</p><button className="traveler-secondary" disabled={busy} onClick={() => perform(() => resume(saved))}>Reprendre la confirmation</button></div>}
      {!confirmationPending && !saved.payment_count && (bank ? <div className="traveler-bank">
        <p>Virement de test via Bridge Demo Bank. La confirmation bancaire déclenchera le chargement.</p>
        {bankUrl ? <><a className="traveler-primary" href={bankUrl} target="_blank" rel="noopener noreferrer">Ouvrir Demo Bank <ArrowRight size={18} /></a><button className="traveler-secondary" disabled={busy} onClick={() => perform(async () => { await api("/orders/" + saved.id + "/bridge/status", "POST", {}); await refreshOrder(saved.id); })}>Vérifier mon paiement</button></> : <button className="traveler-primary" disabled={busy || !!saved.bridge} onClick={() => perform(async () => { await api("/orders/" + saved.id + "/bridge", "POST", {}); await refreshOrder(saved.id); })}>Préparer mon paiement de test <ArrowRight size={18} /></button>}
        {saved.bridge && <p className="small muted">Statut bancaire : {saved.bridge.provider_status || "en préparation"}. Un résultat incertain doit être vérifié avant toute nouvelle tentative.</p>}
      </div> : <><p className="traveler-note">{saved.quote.total_cents === 0 ? "Aucun prépaiement. L’usage du vélo sera facturé après restitution simulée." : "Paiement de démonstration : aucun prélèvement sur une carte bancaire."}</p><button className="traveler-primary" disabled={busy} onClick={() => perform(() => pay(saved))}><CreditCard size={18} />{saved.quote.total_cents === 0 ? "Activer mon accès sans prépaiement" : "Simuler le paiement de " + money(saved.quote.total_cents)}<ArrowRight size={18} /></button></>)}
      {!confirmationPending && saved.payment_count > 0 && !done && <div className="traveler-loading" role="status"><p>{saved.state === "reconciliation_required" ? "Consultez l’agence de démonstration pour rapprocher le résultat de cette opération." : "Vous pouvez quitter cet écran et retrouver la commande dans Mes titres."}</p><button className="traveler-secondary" disabled={busy} onClick={() => perform(() => resume(saved))}>Reprendre le suivi</button></div>}
      {done && <div className="traveler-result"><p><CheckCircle2 size={18} /> Carte simulée chargée et relue avec succès.</p><button className="traveler-primary" onClick={() => { setSelected(""); navigate("tickets"); }}>Retrouver mes titres <Ticket size={18} /></button>{saved.quote.lines.some((line: Data) => ["bike", "parking"].includes(line.product)) && <button className="traveler-secondary" onClick={() => { setServiceOrder(saved.id); navigate("services"); }}>Utiliser mes services <ArrowRight size={18} /></button>}</div>}
    </section>;
  }

  if (!profile) return <div className="traveler-page traveler-login">
    <div className="traveler-topline"><span><Wind size={20} /> ALIZÉ · MON ESPACE</span><span className="badge light">Démo</span></div>
    <div className="traveler-login-layout"><section className="traveler-login-intro"><p className="eyebrow">VOTRE ESPACE VOYAGEUR</p><h1>Vos mobilités.<br /> Un seul compte.</h1><p>Achetez vos titres, retrouvez vos commandes et utilisez vos services vélo et parking.</p><div className="traveler-benefits"><span><ShoppingBag size={18} /> Composez votre panier</span><span><Ticket size={18} /> Retrouvez vos titres</span><span><Bike size={18} /> Accédez à vos services</span></div></section>
      <form className="card traveler-login-card" onSubmit={event => { event.preventDefault(); perform(signIn); }}><span className="traveler-login-icon"><UserRound size={25} /></span><h2>Se connecter</h2><p>Choisissez un compte fictif pour essayer le parcours. Aucun mot de passe ni donnée personnelle à saisir.</p>{messages}<fieldset className="traveler-profiles"><legend>Votre profil de démonstration</legend>{profiles.map(value => <label key={value.id} className={profileChoice === value.id ? "selected" : ""}><input type="radio" name="traveler-profile" checked={profileChoice === value.id} disabled={busy} onChange={() => setProfileChoice(value.id)} /><span className="traveler-avatar" aria-hidden="true">{value.initials}</span><span><strong>{value.name} <small>{value.description}</small></strong><span>{value.detail}</span></span></label>)}</fieldset><button className="traveler-primary" disabled={busy}>{busy ? <LoaderCircle className="traveler-spin" size={18} /> : <UserRound size={18} />}{busy ? "Connexion en cours…" : "Se connecter en démonstration"}<ArrowRight size={18} /></button><p className="traveler-login-footnote">Paiements, titres et services de démonstration. Aucun argent réel.</p></form>
    </div>
  </div>;

  const tabs: { id: Page; title: string; Icon: typeof Ticket }[] = [
    { id: "shop", title: "Acheter", Icon: ShoppingBag },
    { id: "cart", title: "Panier", Icon: ShoppingCart },
    { id: "tickets", title: "Mes titres", Icon: Ticket },
    { id: "services", title: "Mes services", Icon: Bike },
    { id: "help", title: "Aide", Icon: Headphones },
  ];
  return <div className="traveler-page">
    <div className="traveler-account"><div><span className="traveler-avatar" aria-hidden="true">{name.slice(0, 1)}</span><span>Bonjour, <strong>{name}</strong><small>Compte de démonstration · {profile.id === "lea" ? "profil étudiant" : "profil adulte"}</small></span></div><button className="traveler-logout" aria-label="Se déconnecter" disabled={busy} onClick={() => disconnect()}><LogOut size={17} /><span>Se déconnecter</span></button></div>
    <nav className="traveler-nav" aria-label="Mon espace voyageur">{tabs.map(({ id, title, Icon }) => <button key={id} aria-current={page === id || (id === "cart" && page === "checkout") ? "page" : undefined} onClick={() => navigate(id)}><Icon size={18} /><span>{title}</span>{id === "cart" && <b aria-label={products.length + " produits dans le panier"}>{products.length}</b>}</button>)}</nav>
    <div className="traveler-body">{messages}
      {page === "shop" && <><div className="traveler-heading"><p className="eyebrow">À CHAQUE ENVIE, SA MOBILITÉ</p><h1>De quoi avez-vous besoin ?</h1><p>Ajoutez vos produits au panier. Vos réductions seront calculées selon votre profil et la date d’utilisation.</p></div><div className="traveler-products">{catalog?.products.map((product: Data) => {
        const { title, description, Icon } = productInfo[product.id] || { title: product.name, description: "", Icon: Ticket };
        const added = products.includes(product.id);
        return <article className={"card traveler-product " + (added ? "in-cart" : "")} key={product.id}><span className="traveler-product-icon"><Icon size={29} /></span><h2>{title}</h2><p>{description}</p><div className="traveler-price">{product.id === "bike" ? <><strong>Après usage</strong><small>{money(product.unlock_cents)} + {money(product.minute_cents)}/min · plafond {money(product.cap_cents)}</small></> : <><strong>{money(product.price_cents)}</strong><small>{product.id === "transport" ? "Tarif public · réductions dans le panier" : "Une journée"}</small></>}</div><button className="traveler-secondary" disabled={added || busy || uncertain} onClick={() => { updateBasket([...products, product.id]); setInfo(title + " ajouté au panier."); }}>{added ? <Check size={18} /> : <Plus size={18} />}{added ? "Dans le panier" : "Ajouter au panier"}</button></article>;
      })}</div><div className="traveler-shop-bottom"><p><ShoppingCart size={19} /> {products.length ? `${products.length} produit${products.length > 1 ? "s" : ""} dans votre panier` : "Votre panier est prêt à accueillir vos produits."}</p><button className="traveler-primary" disabled={!products.length} onClick={() => navigate("cart")}>Voir mon panier <ArrowRight size={18} /></button></div></>}
      {page === "cart" && <><div className="traveler-heading"><p className="eyebrow">VOTRE ACHAT</p><h1>Mon panier <span className="traveler-count">{products.length}</span></h1><p>Modifiez votre sélection, vérifiez votre tarif, puis confirmez votre commande.</p></div>{!products.length ? <div className="card traveler-empty"><ShoppingCart size={38} /><h2>Votre panier est vide</h2><p>Choisissez un titre ou un service pour commencer.</p><button className="traveler-primary" onClick={() => navigate("shop")}>Découvrir les offres <ArrowRight size={18} /></button></div> : <div className="traveler-cart-layout"><section className="card"><h2>Votre sélection</h2><label className="traveler-date">Date d’utilisation<input type="date" value={travelDate} required disabled={busy || uncertain} onChange={event => updateBasket(products, event.target.value)} /></label>{products.map(id => <div className="traveler-basket-line" key={id}><span className="traveler-mini-icon">{id === "transport" ? <Ticket size={21} /> : id === "parking" ? <CarFront size={21} /> : <Bike size={21} />}</span><div><strong>{productInfo[id]?.title || id}</strong><small>{id === "bike" ? "Facturation après restitution" : "1 titre"}</small></div><button className="traveler-remove" aria-label={"Retirer " + (productInfo[id]?.title || id)} disabled={busy || uncertain} onClick={() => updateBasket(products.filter(value => value !== id))}><Minus size={16} /><span>Retirer</span></button></div>)}<button className="traveler-link" disabled={busy || uncertain} onClick={() => navigate("shop")}><Plus size={16} /> Ajouter d’autres produits</button></section><section className="card traveler-summary" aria-label="Récapitulatif du panier"><h2>Votre récapitulatif</h2><p className="small muted">Tarif pour {name} · {travelDate ? dateLabel(travelDate + "T12:00:00") : "choisissez une date"}</p>{quoting && <p role="status"><LoaderCircle className="traveler-spin" size={18} /> Calcul de votre tarif…</p>}{currentQuote && quote && <>{quote.lines.map((line: Data) => <div className="price-line" key={line.product}><div><strong>{productInfo[line.product]?.title || line.name}</strong><small>{line.product === "bike" ? `${money(line.terms.unlock_cents)} + ${money(line.terms.minute_cents)}/min commencée · plafond ${money(line.terms.cap_cents)}` : line.rule === "standard" ? "Tarif standard" : line.rule}</small></div><b>{line.product === "bike" ? "Après usage" : money(line.amount_cents)}</b></div>)}<div className="total"><span>À payer maintenant</span><strong>{money(quote.total_cents)}</strong></div>{quote.total_cents > 0 && <fieldset className="traveler-payment-options"><legend>Mode de paiement de test</legend><label><input type="radio" name="traveler-payment" checked={paymentMode === "local_simulator"} disabled={busy || uncertain} onChange={() => { setPaymentMode("local_simulator"); setConsent(false); }} /><span>Simulation locale<small>Aucun débit bancaire</small></span></label><label><input type="radio" name="traveler-payment" checked={paymentMode === "bridge_sandbox"} disabled={busy || uncertain || !bridgeEnabled} onChange={() => { setPaymentMode("bridge_sandbox"); setConsent(false); }} /><span>Bridge Demo Bank<small>{bridgeEnabled ? "Virement dans la banque de test" : "Indisponible dans cette configuration"}</small></span></label></fieldset>}{quote.lines.some((line: Data) => line.product === "bike") && <p className="traveler-note">Le vélo sera facturé après usage simulé, en plus du montant à payer maintenant.</p>}{expired && !uncertain && <p role="alert" className="alert error">Votre devis a expiré. Actualisez-le avant de confirmer.</p>}<label className="check traveler-consent"><input type="checkbox" checked={consent} disabled={busy || uncertain || expired} onChange={event => setConsent(event.target.checked)} />Je confirme les produits, la date et le prix affichés{quote.lines.some((line: Data) => line.product === "bike") ? ", ainsi que le tarif vélo après usage." : "."}</label></>}{uncertain && <p role="status" className="traveler-note">Confirmation en attente. Réessayez avec la même commande pour retrouver son résultat.</p>}{!quoting && !uncertain && (!currentQuote || expired) ? <button className="traveler-primary" disabled={busy || !travelDate} onClick={() => setQuoteAttempt(value => value + 1)}>Recalculer mon tarif <ArrowRight size={18} /></button> : <button className="traveler-primary" disabled={busy || quoting || (!uncertain && (!consent || !currentQuote || expired))} onClick={() => perform(confirm)}>{busy ? <LoaderCircle className="traveler-spin" size={18} /> : <Check size={18} />}{uncertain ? "Retrouver ma commande" : "Confirmer ma commande"}<ArrowRight size={18} /></button>}<p className="small muted">La confirmation enregistre votre commande. Le paiement est l’étape suivante.</p></section></div>}</>}
      {page === "checkout" && order && <><button className="traveler-link" onClick={() => navigate("tickets")}><ArrowLeft size={17} /> Mes titres et commandes</button>{orderDetail(order)}</>}
      {page === "tickets" && <><div className="traveler-heading"><p className="eyebrow">VOTRE COMPTE</p><h1>Mes titres et commandes</h1><p>Vos achats sur le site et sur la borne sont réunis ici. Retrouvez leur état et reprenez une commande en attente.</p></div>{!orders.length ? <div className="card traveler-empty"><Ticket size={38} /><h2>Votre premier titre vous attend</h2><p>Vous n’avez pas encore de commande sur ce compte.</p><button className="traveler-primary" onClick={() => navigate("shop")}>Acheter un titre <ArrowRight size={18} /></button></div> : <section className="card traveler-orders"><div className="traveler-section-heading"><h2>{orders.length} commande{orders.length > 1 ? "s" : ""}</h2><button className="traveler-link" disabled={busy} onClick={() => perform(async () => { setOrders(await api("/orders")); setSyncError(""); })}>Actualiser</button></div>{orders.slice(0, visibleOrders).map(saved => <button className="traveler-order" key={saved.id} onClick={() => { setSelected(saved.id); navigate("checkout"); }}><span className="traveler-mini-icon"><Ticket size={22} /></span><span><strong>{saved.quote.lines.map((line: Data) => productInfo[line.product]?.title || line.name).join(" + ")}</strong><small>{dateLabel(saved.created_at)} · {saved.channel === "automate" ? "Achat à la borne" : "Achat sur le site"} · {saved.id.slice(-8)}</small><span className={"status " + (deliveryConfirmed(saved as any) ? "good" : "")}>{orderLabels[saved.state] || "Traitement en cours"}</span></span><span><b>{money(saved.quote.total_cents)}</b><ArrowRight size={17} /></span></button>)}{orders.length > visibleOrders && <button className="traveler-secondary" onClick={() => setVisibleOrders(value => value + 8)}>Afficher plus de commandes</button>}</section>}</>}
      {page === "services" && <><div className="traveler-heading"><p className="eyebrow">VOTRE MOBILITÉ AU QUOTIDIEN</p><h1>Mes services</h1><p>Réservez et utilisez les services associés à vos titres délivrés.</p></div>{activeService ? <section className="card"><label>Choisir une commande avec des services<select value={activeService.id} onChange={event => setServiceOrder(event.target.value)}>{serviceOrders.map(saved => <option key={saved.id} value={saved.id}>{dateLabel(saved.created_at)} · {saved.quote.lines.filter((line: Data) => ["bike", "parking"].includes(line.product)).map((line: Data) => productInfo[line.product]?.title).join(" + ")} · {saved.id.slice(-8)}</option>)}</select></label><PartnerPanel key={profile.id + activeService.id} api={api} order={activeService} aiEnabled={provider !== "disabled"} customer /></section> : <div className="card traveler-empty"><Bike size={38} /><h2>Vos services seront disponibles ici</h2><p>Ajoutez un accès vélo ou un parking à votre panier, puis terminez la délivrance de votre commande.</p><button className="traveler-primary" onClick={() => navigate("shop")}>Découvrir les services <ArrowRight size={18} /></button></div>}</>}
      {page === "help" && <><div className="traveler-heading"><p className="eyebrow">UN COUP DE MAIN ?</p><h1>Comment pouvons-nous vous aider ?</h1><p>Posez une question sur les tarifs ou sur l’une de vos commandes.</p></div><section className="card traveler-help-context"><label>Votre question concerne<select value={selected} onChange={event => setSelected(event.target.value)}><option value="">Les offres et tarifs</option>{orders.map(saved => <option key={saved.id} value={saved.id}>Commande {saved.id.slice(-8)} · {money(saved.quote.total_cents)}</option>)}</select></label></section><Assistant key={profile.id} api={api} orderId={selected || undefined} runtimeProvider={provider} customer travelerId={profile.id} travelDate={travelDate} onProposal={proposal => { if (busy || uncertain || proposal.traveler !== profile.id || proposal.seller !== "app") return; updateBasket(proposal.lines.map((line: Data) => line.product), proposal.travel_date); navigate("cart"); }} /><details className="traveler-about"><summary>À propos de cette démonstration</summary><DemoScope provider={provider} bridgeEnabled={bridgeEnabled} /></details></>}
      <AgentActivity key={profile.id} api={api} />
      <footer className="traveler-footer"><span>ALIZÉ · COMPTE DE DÉMONSTRATION</span><span>Aucun argent réel · Carte et équipements simulés</span></footer>
    </div>
  </div>;
}
