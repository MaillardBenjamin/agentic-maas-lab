import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Bike, CarFront, Check, CheckCircle2, CreditCard, Headphones, LoaderCircle, LogOut, Nfc, ShieldCheck, Ticket, Wind } from "lucide-react";
import { Assistant } from "./Assistant";
import { DemoScope, type AIProvider } from "./DemoScope";
import { QRCodeSVG } from "qrcode.react";
import { bankScreenSeconds, bridgePaymentUrl, idleSeconds, kioskStep, quoteExpired } from "./kiosk-state";
import "./kiosk.css";

type Data = Record<string, any>;
const money = (c: number) => new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(c / 100);
const offers = [
  { id: "transport", title: "Transport Alizé", subtitle: "Un titre pour le réseau fictif", Icon: Ticket },
  { id: "parking", title: "Parking relais", subtitle: "Une journée de stationnement", Icon: CarFront },
  { id: "bike", title: "Vélo partagé", subtitle: "Facturé après l’usage simulé", Icon: Bike },
];
const stages = ["Votre carte", "Vos titres", "Paiement", "Chargement"];
function localDate() {
  const d = new Date();
  return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, "0"), String(d.getDate()).padStart(2, "0")].join("-");
}
class RequestError extends Error {
  constructor(public detail: any) { super(typeof detail === "string" ? detail : detail?.message || "Service temporairement indisponible."); }
}
class OldSession extends Error {}

export function Kiosk({ provider, bridgeEnabled }: { provider: AIProvider; bridgeEnabled: boolean }) {
  const [traveler, setTraveler] = useState("lea");
  const [profile, setProfile] = useState<Data | null>(null);
  const [auth, setAuth] = useState("");
  const [products, setProducts] = useState(["transport", "parking", "bike"]);
  const [quote, setQuote] = useState<Data | null>(null);
  const [order, setOrder] = useState<Data | null>(null);
  const [paymentMode, setPaymentMode] = useState("bridge_sandbox");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [closed, setClosed] = useState("");
  const [remaining, setRemaining] = useState(120);
  const [help, setHelp] = useState(false);
  const epoch = useRef(0), lock = useRef(false), lastActivity = useRef(Date.now());
  const purchase = useRef<Data | null>(null);
  const helpDialog = useRef<HTMLDialogElement>(null);
  const step = kioskStep(!!profile, !!quote, order as any);
  const bankMode = order?.payment_mode === "bridge_sandbox";
  const bankUrl = bridgePaymentUrl(order?.bridge?.url);
  const bankExpiry = bankMode && !order?.payment_count ? order?.bridge?.expires_at : undefined;
  const name = profile?.id === "adult" ? "Alex" : "Léa";
  const stageIndex = step === "welcome" ? 0 : step === "products" || step === "review" ? 1 : step === "payment" ? 2 : 3;

  useEffect(() => () => { epoch.current++; }, []);
  useEffect(() => {
    if (help) helpDialog.current?.showModal();
    else helpDialog.current?.close();
  }, [help]);

  function activity() { lastActivity.current = Date.now(); setRemaining(120); }
  function reset(message: string) {
    epoch.current++;
    setProfile(null); setAuth(""); setQuote(null); setOrder(null);
    setProducts(["transport", "parking", "bike"]); setTraveler("lea");
    setPaymentMode("bridge_sandbox"); setConsent(false); setHelp(false); setError(""); setInfo("");
    setClosed(message); purchase.current = null; activity();
  }
  useEffect(() => {
    if (!profile) return;
    lastActivity.current = Date.now();
    const timer = setInterval(() => {
      if (lock.current) { lastActivity.current = Date.now(); return; }
      const left = bankExpiry ? bankScreenSeconds(bankExpiry) : idleSeconds(lastActivity.current);
      setRemaining(left);
      if (left === 0) reset("Session fermée après inactivité. Les commandes engagées sont conservées dans le POC.");
    }, 1000);
    return () => clearInterval(timer);
  }, [!!profile, bankExpiry]);

  async function api(path: string, method = "GET", body?: Data, bearer = auth) {
    const version = epoch.current;
    let response: Response;
    try {
      response = await fetch("/api" + path, { method, headers: { "Content-Type": "application/json", ...(bearer ? { Authorization: "Bearer " + bearer } : {}) }, body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(path === "/chat" ? 310000 : 20000) });
    } catch (e) {
      if (epoch.current !== version) throw new OldSession();
      throw new RequestError("Le service n’a pas répondu. Réessayez ou consultez l’agence de démonstration.");
    }
    const value = await response.json().catch(() => ({}));
    if (epoch.current !== version) throw new OldSession();
    if (!response.ok) throw new RequestError(value.detail || "La demande n’a pas abouti. Réessayez ou consultez l’agence.");
    return value;
  }
  async function perform(fn: () => Promise<void>) {
    if (lock.current) return;
    const version = epoch.current;
    lock.current = true; setBusy(true); setError(""); setInfo(""); activity();
    try { await fn(); }
    catch (e) { if (epoch.current === version && !(e instanceof OldSession)) setError((e as Error).message); }
    finally { lock.current = false; if (epoch.current === version) setBusy(false); }
  }
  useEffect(() => {
    if (!order?.id || !auth) return;
    let alive = true;
    const version = epoch.current;
    async function refresh() {
      if (!alive || epoch.current !== version) return;
      try {
        const next = await api("/orders/" + order!.id);
        if (alive && epoch.current === version) setOrder(next);
      } catch (e) {
        if (alive && epoch.current === version && !(e instanceof OldSession)) setError("Suivi indisponible. La commande est conservée ; utilisez « Reprendre le suivi ».");
      }
    }
    const timer = setInterval(refresh, 1500);
    return () => { alive = false; clearInterval(timer); };
  }, [order?.id, auth]);

  async function present() {
    const data = await api("/demo/login/" + traveler, "POST", undefined, "");
    setAuth(data.access_token); setProfile(data.user); setClosed(""); activity();
  }
  async function calculate() {
    const q = await api("/quotes", "POST", { traveler: profile!.id, products, seller: "agency", travel_date: localDate() });
    purchase.current = { quote_id: q.id, idempotency_key: "kiosk-" + crypto.randomUUID(), channel: "automate", pause_before_issue: false, payment_mode: "local_simulator" };
    setQuote(q); setConsent(false);
  }
  async function confirm() {
    if (!consent || !quote || !purchase.current) return;
    if (quoteExpired(quote.expires_at)) { setQuote(null); setConsent(false); throw new RequestError("Le devis a expiré. Recalculez votre offre."); }
    purchase.current.payment_mode = quote.total_cents === 0 ? "local_simulator" : paymentMode;
    try { setOrder(await api("/orders", "POST", purchase.current)); }
    catch (e) {
      if (e instanceof RequestError && e.detail?.order_id) setOrder(await api("/orders/" + e.detail.order_id));
      throw e;
    }
  }
  async function bankLink() {
    await api("/orders/" + order!.id + "/bridge", "POST", {});
    setOrder(await api("/orders/" + order!.id));
  }
  async function checkBank() {
    await api("/orders/" + order!.id + "/bridge/status", "POST", {});
    setOrder(await api("/orders/" + order!.id));
  }
  async function pay() {
    if (bankMode) { await checkBank(); return; }

    try { await api("/demo/orders/" + order!.id + "/pay", "POST", {}); }
    catch (e) {
      const saved = await api("/orders/" + order!.id);
      setOrder(saved);
      if (!saved.payment_count) throw e;
      setInfo("Paiement fictif enregistré. Le chargement peut être repris sans second paiement.");
      return;
    }
    setOrder(await api("/orders/" + order!.id));
  }
  async function resume() {
    if (!purchase.current || !order) return;
    await api("/orders", "POST", purchase.current);
    const saved = await api("/orders/" + order.id);
    setOrder(saved);
    if (saved.state !== "fulfilled" && saved.payment_count > 0) {
      if (saved.state === "awaiting_resume") await api("/demo/orders/" + order.id + "/continue", "POST", {});
      else await pay();
    }
    if (saved.payment_mode === "bridge_sandbox" && !saved.payment_count) await bankLink();
    setInfo("Suivi repris. Le POC conserve la même commande et la même opération de chargement.");
  }

  return (
    <div className="kiosk-page" onPointerDown={activity} onKeyDown={activity} onWheel={activity}>
      <div className="kiosk-caption"><span>BORNE DE VENTE · SIMULATION INTERACTIVE</span><span>Canal automate · aucun argent réel</span></div>
      <div className="kiosk-machine">
        <div className="kiosk-crown"><span><Wind size={27} /> alizé <small>LES MOBILITÉS, SIMPLEMENT.</small></span><b>AZ–01 <i /></b></div>
        <div className="kiosk-screen">
          <div className="kiosk-screen-header"><span>Votre point de vente Alizé <small>Station de démonstration</small></span><div><span className="kiosk-language">FR</span><button disabled={!profile || busy} onClick={() => setHelp(true)}><Headphones size={18} /> Assistance IA</button></div></div>
          <ol className="kiosk-progress" aria-label="Étapes de l’achat">
            {stages.map((label, i) => <li key={label} className={i === stageIndex ? "current" : i < stageIndex ? "passed" : ""} aria-current={i === stageIndex ? "step" : undefined}><span>{i < stageIndex ? <Check size={14} /> : i + 1}</span><b>{label}</b></li>)}
          </ol>
          {error && <p role="alert" className="kiosk-message kiosk-error">{error}</p>}
          {info && <p role="status" className="kiosk-message">{info}</p>}
          {profile && remaining <= 20 && <div role="alert" className="kiosk-idle">Fin de session dans {remaining} s sans intervention.<button onClick={activity}>Continuer ma session</button></div>}
          <div className="kiosk-stage" aria-busy={busy}>
            {step === "welcome" && <div className="kiosk-welcome">
              <div><p className="kiosk-eyebrow">BONJOUR & BIENVENUE</p><h1>Vos titres, à portée de carte.</h1><p>Présentez votre carte de démonstration pour choisir et charger vos titres.</p>
                <fieldset className="kiosk-profiles"><legend>Choisir une carte fictive</legend>{[["lea", "Léa", "Profil étudiant de démo"], ["adult", "Alex", "Profil adulte de démo"]].map(([id, n, description]) => <label key={id} className={traveler === id ? "selected" : ""}><input type="radio" name="kiosk-profile" value={id} checked={traveler === id} disabled={busy} onChange={() => setTraveler(id)} /><span><strong>{n}</strong><small>{description}</small></span></label>)}</fieldset>
                <button className="kiosk-primary" disabled={busy} onClick={() => perform(present)}>{busy ? <LoaderCircle className="kiosk-spin" /> : <Nfc />} Simuler la présentation de carte <ArrowRight size={20} /></button>
                {closed && <p role="status" className="kiosk-session-message">{closed}</p>}
              </div>
              <div className="kiosk-card-art" aria-hidden="true"><div><Wind size={28} /><strong>alizé</strong><span>VOTRE CARTE MOBILITÉ</span><Nfc size={36} /><small>CARTE DE DÉMONSTRATION</small></div><span className="kiosk-contactless-rings" /></div>
            </div>}
            {step === "products" && <>
              <p className="kiosk-eyebrow">CARTE PRÉSENTÉE · {name.toUpperCase()}</p><h1>De quoi avez-vous besoin ?</h1><p>Choisissez vos produits. Le prix exact sera calculé selon le profil fictif de votre carte.</p>
              <div className="kiosk-products">{offers.map(({ id, title, subtitle, Icon }) => <button key={id} aria-pressed={products.includes(id)} disabled={busy} onClick={() => setProducts(list => list.includes(id) ? list.filter(p => p !== id) : [...list, id])}><span className="kiosk-product-check">{products.includes(id) && <Check size={16} />}</span><Icon size={32} /><strong>{title}</strong><small>{subtitle}</small></button>)}</div>
              <div className="kiosk-stage-actions"><span>{products.length} produit(s) sélectionné(s)</span><button className="kiosk-primary" disabled={busy || !products.length} onClick={() => perform(calculate)}>Voir mon tarif <ArrowRight size={20} /></button></div>
            </>}
            {step === "review" && quote && <>
              <p className="kiosk-eyebrow">VOTRE OFFRE · {name.toUpperCase()}</p><h1>Vérifiez avant de payer.</h1>
              <div className="kiosk-quote">{quote.lines.map((line: Data) => <div key={line.product}><span><strong>{line.name}</strong><small>{line.product === "bike" ? `${money(line.terms.unlock_cents)} + ${money(line.terms.minute_cents)}/min commencée · plafond ${money(line.terms.cap_cents)}` : line.rule === "standard" ? "Tarif standard" : line.rule}</small></span><b>{line.product === "bike" ? "Après usage" : money(line.amount_cents)}</b></div>)}<div className="kiosk-total"><span>À payer maintenant <small>{quote.total_cents === 0 ? "Aucun prépaiement" : paymentMode === "bridge_sandbox" ? "Virement Bridge sandbox par QR code" : "Terminal CB simulé · aucun débit"}</small></span><strong>{money(quote.total_cents)}</strong></div></div>
              {quote.total_cents > 0 && <fieldset className="kiosk-payment-choice"><legend>Choisissez votre paiement de démonstration</legend><label><input type="radio" name="payment-mode" checked={paymentMode === "bridge_sandbox"} disabled={busy} onChange={() => setPaymentMode("bridge_sandbox")} /> QR code · virement Bridge sandbox {bridgeEnabled ? "" : "(indisponible : configurer Bridge)"}</label><label><input type="radio" name="payment-mode" checked={paymentMode === "local_simulator"} disabled={busy} onChange={() => setPaymentMode("local_simulator")} /> Terminal CB · simulation locale</label><small>Bridge initie un virement bancaire. Il ne traite pas la carte CB de ce terminal.</small></fieldset>}
              <label className="kiosk-consent"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} disabled={busy} />Je confirme les produits et le prix affichés.</label>
              <div className="kiosk-stage-actions"><button className="kiosk-secondary" disabled={busy} onClick={() => { setQuote(null); setConsent(false); }}><ArrowLeft size={18} /> Modifier mes titres</button><button className="kiosk-primary" disabled={busy || !consent || (quote.total_cents > 0 && paymentMode === "bridge_sandbox" && !bridgeEnabled)} onClick={() => perform(confirm)}>Confirmer et passer au paiement <ArrowRight size={18} /></button></div>
            </>}
            {step === "payment" && order && (bankMode ? <div className="kiosk-payment kiosk-bank"><div><p className="kiosk-eyebrow">VIREMENT OPEN BANKING · SANDBOX</p><h1>Scannez et payez sur votre téléphone.</h1><p>Le QR code ouvre Bridge et sa Demo Bank. Aucun argent réel ne circule. Validez le virement sur votre téléphone, puis attendez ici la confirmation bancaire.</p><strong className="kiosk-amount">{money(order.quote.total_cents)}</strong><p role="status">{order.bridge?.provider_status === "RJCT" ? "Virement refusé. Aucun titre chargé ; consultez l’agence de démonstration." : order.bridge?.provider_status === "PDNG" ? "Virement en attente de règlement bancaire." : "En attente de confirmation de la banque. Aucun titre chargé."}</p>{bankExpiry && <p>Lien valable encore {Math.floor(remaining / 60)} min {remaining % 60} s. Le suivi serveur continue après fermeture de cet écran, jusqu’à 15 min.</p>}<button className="kiosk-secondary" disabled={busy} onClick={() => perform(resume)}>Reprendre le suivi</button></div><div className="kiosk-qr">{bankUrl ? <><QRCodeSVG value={bankUrl} size={240} level="M" marginSize={4} title="Lien public de paiement Bridge sandbox" /><a href={bankUrl} target="_blank" rel="noopener noreferrer">Ouvrir le lien de test sur ce poste</a><button className="kiosk-link" disabled={busy} onClick={() => perform(checkBank)}>Vérifier le statut bancaire</button><small>Seule une confirmation bancaire du montant et de la référence autorise le chargement.</small></> : <><ShieldCheck size={52} /><button className="kiosk-primary" disabled={busy} onClick={() => perform(bankLink)}>Afficher le QR code Bridge</button><small>Un lien public de test sera créé. Aucune clé bancaire n’est contenue dans le QR code.</small></>}</div></div> : <div className="kiosk-payment"><div><p className="kiosk-eyebrow">{order.quote.total_cents === 0 ? "SANS PRÉPAIEMENT" : "TERMINAL CB · SIMULATION LOCALE"}</p><h1>Un dernier geste.</h1><p>{order.quote.total_cents === 0 ? "L’usage du vélo sera facturé après utilisation simulée. Aucun paiement initial n’est nécessaire." : "Le terminal dessiné ci-dessous est fictif. Le bouton simule un paiement CB, sans PSP ni appel à Bridge."}</p><strong className="kiosk-amount">{money(order.quote.total_cents)}</strong><button className="kiosk-primary" disabled={busy} onClick={() => perform(pay)}><CreditCard size={22} />{order.quote.total_cents === 0 ? "Confirmer le chargement sans prépaiement" : "Simuler le paiement sur le terminal"}</button><button className="kiosk-link" disabled={busy} onClick={() => perform(resume)}>Reprendre le suivi de la commande</button></div><div className="kiosk-payment-symbol" aria-hidden="true"><CreditCard size={64} /><span>AUCUN DÉBIT RÉEL</span></div></div>)}
            {step === "loading" && order && <div className="kiosk-loading" role="status"><LoaderCircle className="kiosk-spin" size={48} /><h1>Le chargement est en cours.</h1><p>Gardez votre carte sur le lecteur simulé. Cet écran attend la confirmation du service de délivrance.</p><p className="kiosk-load-status">{order.state === "reconciliation_required" ? "Rapprochement nécessaire : consultez l’agence de démonstration." : order.state === "fulfilled" ? "La relecture de carte doit encore être vérifiée." : order.state === "awaiting_resume" ? "Le workflow attend un signal de reprise." : "Paiement enregistré · confirmation du chargement attendue"}</p><button className="kiosk-secondary" disabled={busy} onClick={() => perform(resume)}>Reprendre le suivi</button></div>}
            {step === "done" && order && <div className="kiosk-done"><CheckCircle2 size={56} /><p className="kiosk-eyebrow">CHARGEMENT CONFIRMÉ</p><h1>Votre carte est prête, {name}.</h1><p>Le SDK Keyple a écrit et relu votre carte simulée.</p><div className="kiosk-receipt"><span>Commande <b>{order.id.slice(-12)}</b></span><span>{bankMode ? "Virement Bridge sandbox" : order.quote.total_cents === 0 ? "Sans prépaiement" : "CB simulée"} <b>{money(order.quote.total_cents)}</b></span><span>Chargement de carte <b>{order.card.load_count} · relecture vérifiée</b></span></div><button className="kiosk-primary" onClick={() => reset("Merci. La session est terminée et la borne est prête pour le prochain voyageur.")}>Retirer ma carte et terminer <ArrowRight size={20} /></button><p className="kiosk-next">Pour réserver un vélo ou utiliser le parking, retrouvez cette commande dans l’espace Voyageur avec la même identité de démo.</p></div>}
          </div>
          <div className="kiosk-screen-footer"><span><ShieldCheck size={15} /> Carte, lecteur et terminal simulés</span>{profile && <><span>{bankExpiry ? "Session maintenue pendant la validité du QR code" : "Session d’écran · retour après 2 min d’inactivité"}</span><button disabled={busy} onClick={() => reset("Session terminée. Les commandes déjà engagées restent conservées dans le POC.")}><LogOut size={15} /> Terminer la session</button></>}</div>
        </div>
        <div className="kiosk-hardware">
          <button className={"kiosk-reader " + (profile ? "card-present" : "")} disabled={busy || !!profile} onClick={() => perform(present)} aria-label="Simuler la présentation sur le lecteur de carte"><Nfc size={34} /><span>{profile ? step === "done" ? "REPRENEZ VOTRE CARTE" : "CARTE PRÉSENTÉE" : "POSEZ VOTRE CARTE"}<small>Lecteur sans contact fictif</small></span><i /></button>
          <div className="kiosk-terminal" aria-label="Terminal de paiement fictif"><div><CreditCard size={22} /><span>{step === "payment" ? "PRÊT POUR LE TEST" : "TERMINAL FICTIF"}<small>Aucun débit bancaire</small></span></div><span className="kiosk-keypad" aria-hidden="true">{Array.from({ length: 9 }, (_, i) => <i key={i} />)}</span></div>
          <div className="kiosk-slot" aria-hidden="true"><span /><small>AZ–01 · BORNE DE LABORATOIRE</small></div>
        </div>
      </div>
      <details className="kiosk-explainer"><summary>Comprendre cette simulation de borne</summary><p>La présentation de carte sélectionne une identité fictive. Les tarifs et commandes utilisent les API métier ; Temporal et le SDK Keyple effectuent réellement le parcours sur une carte stub. Le paiement par QR code utilise un vrai échange avec Bridge sandbox et sa Demo Bank, sans argent réel. Le terminal CB est une simulation locale distincte, sans PSP connecté. Temporal contrôle le statut bancaire pendant 15 minutes, même si cet écran est fermé ; au-delà, un contrôle manuel en agence est nécessaire si le règlement est tardif.</p><p>Terminer la session efface son affichage et son contexte local, sans supprimer la commande. Le retour automatique n’annule pas les opérations déjà engagées. Cette borne de démonstration ne constitue pas un automate physique certifié.</p><DemoScope provider={provider} bridgeEnabled={bridgeEnabled} /></details>
      <dialog ref={helpDialog} className="kiosk-help" onClose={() => setHelp(false)} onCancel={() => setHelp(false)}><div className="kiosk-help-header"><strong>Votre assistance à la borne</strong><button onClick={() => setHelp(false)}>Fermer l’assistance</button></div><p>Les agents peuvent expliquer les offres et votre commande. Vous choisissez et confirmez les opérations sur l’écran de la borne. La voix reste expérimentale.</p><Assistant key={profile?.id || "welcome"} api={api} runtimeProvider={provider} orderId={order?.id} /></dialog>
    </div>
  );
}
