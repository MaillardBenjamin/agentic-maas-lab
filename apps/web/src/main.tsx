import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Wind,
  Ticket,
  Monitor,
  Headphones,
  Activity,
  ArrowUpRight,
  Check,
  ShieldCheck,
  Clock,
  Search,
  CreditCard,
  Bike,
  CarFront,
  Radio,
  RefreshCw,
} from "lucide-react";
import "./style.css";
import { Assistant } from "./Assistant";
import { DemoScope, type AIProvider } from "./DemoScope";
import { PartnerPanel } from "./PartnerPanel";
import { Kiosk } from "./Kiosk";

type Data = Record<string, any>;
const money = (c: number) =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(
    c / 100,
  );
const labels: Data = {
  payment_pending: "Paiement attendu",
  paid: "Paiement confirmé",
  awaiting_resume: "En attente de reprise",
  issuance_pending: "Chargement en cours",
  fulfilled: "Droit délivré",
  reconciliation_required: "Rapprochement requis",
};

function App() {
  const [view, setView] = useState("voyageur"),
    [identity, setIdentity] = useState("lea"),
    [token, setToken] = useState(""),
    [orders, setOrders] = useState<Data[]>([]),
    [selected, setSelected] = useState(""),
    [q, setQ] = useState<Data | null>(null),
    [statement, setStatement] = useState<Data | null>(null),
    [audit, setAudit] = useState<Data[]>([]),
    [integrations, setIntegrations] = useState<Data[]>([]),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [consent, setConsent] = useState(false),
    [pause, setPause] = useState(true),
    [seller, setSeller] = useState("agency"),
    [query, setQuery] = useState("étudiant réduction"),
    [sources, setSources] = useState<Data[]>([]),
    [refund, setRefund] = useState("2.00");
  const order = orders.find((o) => o.id === selected);
  const [proofs, setProofs] = useState<Data[]>([]),
    [paymentMode, setPaymentMode] = useState("local_simulator");
  const provider: AIProvider = integrations.some(i => i.name === "Ollama" && i.mode === "configured")
    ? "ollama"
    : integrations.some(i => i.name === "OpenAI" && i.mode === "configured") ? "openai" : "disabled";
  const bridgeEnabled = integrations.some(i => i.name === "Bridge" && i.mode === "configured");
  async function api(path: string, method = "GET", body?: Data, t = token) {
    const res = await fetch("/api" + path, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(t ? { Authorization: "Bearer " + t } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json();
    if (!res.ok)
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail),
      );
    return data;
  }
  async function login(id: string) {
    setToken("");
    setOrders([]);
    setSelected("");
    setAudit([]);
    setNotice("");
    const data = await api("/demo/login/" + id, "POST", undefined, "");
    setToken(data.access_token);
    setIdentity(id);
    setQ(null);
    setConsent(false);
    setError("");
  }
  useEffect(() => {
    login("lea").catch((e) => setError(e.message));
  }, []);
  async function refresh() {
    if (!token) return;
    const [o, i] = await Promise.all([api("/orders"), api("/integrations")]);
    setOrders(o);
    setIntegrations(i);
    if (["sav", "console"].includes(view)) setAudit(await api("/audit"));
    if (view === "console") setProofs(await api("/proofs"));
    if (selected) setStatement(await api("/orders/" + selected + "/statement"));
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    const id = setInterval(() => refresh().catch(() => {}), 2500);
    return () => clearInterval(id);
  }, [token, selected, view]);
  async function action(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function changeView(v: string) {
    setView(v);
    window.scrollTo(0, 0);
    setStatement(null);
    login(v === "sav" ? "clerk" : v === "console" ? "demo" : "lea").catch((e) =>
      setError(e.message),
    );
  }
  async function getQuote() {
    setQ(
      await api("/quotes", "POST", {
        traveler: identity,
        products: ["transport", "parking", "bike"],
        seller,
        travel_date: "2026-10-24",
      }),
    );
    setConsent(false);
  }
  async function buy() {
    if (!q || !consent) return;
    const id = "purchase-" + q.id;
    const o = await api("/orders", "POST", {
      quote_id: q.id,
      idempotency_key: id,
      channel: view === "automate" ? "automate" : "web",
      pause_before_issue: pause,
      payment_mode: paymentMode,
    });
    setSelected(o.id);
    setNotice(
      paymentMode === "bridge_sandbox"
        ? "Commande confirmée. Initiez ensuite le paiement dans Demo Bank."
        : "Commande confirmée. Le paiement est encore à simuler.",
    );
  }
  async function event(type: string, suffix: string, extra: Data = {}) {
    await api("/events", "POST", {
      specversion: "1.0",
      id: "manufacturer-" + selected + "-" + suffix,
      source: type.includes("validation")
        ? "urn:manufacturer:x"
        : type.includes("bike")
          ? "urn:partner:bike"
          : "urn:partner:parking",
      type,
      time: "2026-10-24T09:00:00Z",
      data: {
        order_id: selected,
        passage_id: selected + "-" + suffix,
        ...extra,
      },
    });
    setNotice(
      "Événement traité ; le renvoyer permet de tester la déduplication.",
    );
  }
  const nav = [
    ["voyageur", "Voyageur", Ticket],
    ["automate", "Automate", Monitor],
    ["sav", "Agence & SAV", Headphones],
    ["console", "Console", Activity],
  ] as const;
  return (
    <div className="shell">
      <aside>
        <a className="logo" href="#">
          <Wind size={31} /> alizé<span>LAB</span>
        </a>
        <p className="aside-title">MOBILITÉ AUGMENTÉE</p>
        <nav>
          {nav.map(([id, title, Icon]) => (
            <button
              key={id}
              className={view === id ? "active" : ""}
              onClick={() => changeView(id)}
            >
              <Icon size={18} />
              {title}
            </button>
          ))}
        </nav>
        <div className="aside-bottom">
          <span className="dot" /> Démonstrateur local
          <p>
            Données fictives · MIT
            <br />
            Version 0.1 · premier socle
          </p>
        </div>
      </aside>
      <main>
        {view !== "automate" && <header>
          <span>
            ESPACE DE DÉMONSTRATION <span className="slash">/</span>{" "}
            {nav.find((n) => n[0] === view)?.[1]}
          </span>
          <div>
            <span className="badge">Aucun argent réel</span>
            <button
              className="icon"
              aria-label="Actualiser"
              onClick={() => action(refresh)}
            >
              <RefreshCw size={17} />
            </button>
          </div>
        </header>}
        {view === "automate" ? <Kiosk provider={provider} bridgeEnabled={bridgeEnabled} /> : <div className="content">
          <div className="intro">
            <div>
              <p className="eyebrow">MAAS AGENTIQUE</p>
              <h1>
                {view === "sav"
                  ? "Chaque incident a une histoire."
                  : view === "console"
                    ? "Les opérations, à livre ouvert."
                    : "Votre mobilité, en un seul endroit."}
              </h1>
              <p>
                {view === "console"
                  ? "Console technique : suivez Temporal, les preuves A2A/MCP et les événements de passage fictifs. Les valideurs physiques X/Y ne sont pas connectés."
                  : view === "sav"
                    ? "Espace conseiller : retrouvez les dossiers et enregistrez des régularisations comptables fictives dans votre délégation. Aucun remboursement bancaire n’est exécuté."
                    : "Espace personnel sur site ou application : retrouvez vos commandes et utilisez les agents vélo/parking après délivrance. Pour simuler une borne tactile, choisissez Automate."}
              </p>
            </div>
            <div className="stamp">
              <Radio size={19} /> LABORATOIRE
              <br />
              <small>Parcours Alizé</small>
            </div>
          </div>
          {integrations.length > 0 && (
            <DemoScope
              key={view}
              provider={provider}
              bridgeEnabled={bridgeEnabled}
              expanded={view === "console"}
            />
          )}
          {error && (
            <div role="alert" className="alert error">
              {error}
            </div>
          )}
          {notice && (
            <div role="status" className="alert success">
              <Check size={17} />
              {notice}
            </div>
          )}
          <Assistant
            key={identity}
            api={api}
            runtimeProvider={provider}
            agent={
              view === "sav"
                ? "sav"
                : view === "console"
                  ? "clearing"
                  : "conversation"
            }
            orderId={selected}
          />
          {view === "voyageur" && (
            <label className="card payment-choice">
              Mode de paiement de la commande
              <select
                value={paymentMode}
                onChange={(e) => setPaymentMode(e.target.value)}
              >
                <option value="local_simulator">
                  Simulation locale · sans banque
                </option>
                <option
                  value="bridge_sandbox"
                  disabled={!bridgeEnabled}
                >
                  {bridgeEnabled ? "Bridge Demo Bank · sandbox activée" : "Bridge Demo Bank · sandbox à configurer"}
                </option>
              </select>
            </label>
          )}
          <div className="toolbar">
            <label>
              Identité de démonstration{" "}
              <select
                value={identity}
                onChange={(e) =>
                  login(e.target.value).catch((e) => setError(e.message))
                }
              >
                {(view === "sav"
                  ? ["clerk", "supervisor"]
                  : view === "console"
                    ? ["demo"]
                    : ["lea", "adult"]
                ).map((id) => (
                  <option key={id} value={id}>
                    {
                      {
                        lea: "Léa · étudiante",
                        adult: "Alex · adulte",
                        clerk: "Camille · conseiller (5 €)",
                        supervisor: "Sam · superviseur",
                        demo: "Console technique",
                      }[id as "lea"]
                    }
                  </option>
                ))}
              </select>
            </label>
            <span className="muted">Identité locale simulée</span>
          </div>
          {view === "voyageur" && (
            <div className="grid">
              <section className="card">
                <div className="card-heading">
                  <span className="number">01</span>
                  <h2>Composer votre offre</h2>
                  <span className="badge light">Parcours fixe</span>
                </div>
                <div className="journey">
                  <div>
                    <CarFront />
                    <strong>Parking relais</strong>
                    <span>Une journée</span>
                  </div>
                  <i />
                  <div>
                    <Ticket />
                    <strong>Transport Alizé</strong>
                    <span>Réseau fictif</span>
                  </div>
                  <i />
                  <div>
                    <Bike />
                    <strong>Vélo partagé</strong>
                    <span>Après usage</span>
                  </div>
                </div>
                <label>
                  Vendeur
                  <select
                    value={seller}
                    onChange={(e) => {
                      setSeller(e.target.value);
                      setQ(null);
                    }}
                  >
                    <option value="agency">
                      Agence Alizé · commission 5 %
                    </option>
                    <option value="app">
                      Application MaaS · commission 2 %
                    </option>
                  </select>
                </label>
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() => action(getQuote)}
                >
                  Calculer mon offre <ArrowUpRight size={17} />
                </button>
                <p className="small muted">
                  Prix calculés par les règles métier.{" "}
                  {provider === "disabled"
                    ? "Le dialogue IA est désactivé dans la configuration."
                    : "Les agents IA peuvent les expliquer dans l’espace de dialogue."}
                </p>
              </section>
              <section className="card quote">
                <div className="card-heading">
                  <span className="number">02</span>
                  <h2>Votre proposition</h2>
                </div>
                {q ? (
                  <>
                    <p className="small">Version {q.version}</p>
                    {q.lines.map((l: Data) => (
                      <div className="price-line" key={l.product}>
                        <div>
                          <strong>{l.name}</strong>
                          <small>
                            {l.rule === "standard"
                              ? l.product === "bike"
                                ? "1 € + 0,20 €/min, plafond 5 €"
                                : l.rule
                              : l.rule}
                          </small>
                        </div>
                        <b>
                          {l.product === "bike"
                            ? "À l’usage"
                            : money(l.amount_cents)}
                        </b>
                      </div>
                    ))}
                    <div className="total">
                      <span>À payer avant usage</span>
                      <strong>{money(q.total_cents)}</strong>
                    </div>
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={consent}
                        onChange={(e) => setConsent(e.target.checked)}
                      />{" "}
                      Je confirme les produits et le prix de ce devis.
                    </label>
                    <label className="check small">
                      <input
                        type="checkbox"
                        checked={pause}
                        onChange={(e) => setPause(e.target.checked)}
                      />{" "}
                      Pause de démonstration après paiement
                    </label>
                    <button
                      className="primary"
                      disabled={busy || !consent}
                      onClick={() => action(buy)}
                    >
                      Confirmer la commande <CreditCard size={17} />
                    </button>
                  </>
                ) : (
                  <div className="empty">
                    <Ticket size={38} />
                    <p>Votre devis apparaîtra ici.</p>
                    <span>
                      Les réductions sont évaluées à la date du voyage.
                    </span>
                  </div>
                )}
              </section>
            </div>
          )}
          <section className="card">
            <div className="card-heading">
              <span className="number">{view === "console" ? "01" : "03"}</span>
              <h2>
                {view === "sav"
                  ? "Dossiers et commandes"
                  : "Commandes du parcours"}
              </h2>
              <span className="badge light">État persistant</span>
            </div>
            {orders.length === 0 ? (
              <p className="muted">Aucune commande pour cette identité.</p>
            ) : (
              <div className="order-list">
                {orders.map((o) => (
                  <button
                    key={o.id}
                    className={"order " + (selected === o.id ? "selected" : "")}
                    onClick={() => setSelected(o.id)}
                  >
                    <div>
                      <strong>
                        {o.traveler === "lea" ? "Léa" : "Alex"} ·{" "}
                        {money(o.quote.total_cents)}
                      </strong>
                      <small>
                        {o.id.slice(-12)} · {{ web: "Site / application", automate: "Borne simulée", agency: "Agence" }[o.channel as string] || o.channel}
                      </small>
                    </div>
                    <span
                      className={
                        "status " + (o.state === "fulfilled" ? "good" : "")
                      }
                    >
                      {labels[o.state] || o.state}
                    </span>
                  </button>
                ))}
              </div>
            )}
            {order && (
              <div className="order-detail">
                <div className="steps">
                  {["Paiement", "Chargement", "Délivrance"].map((l, i) => (
                    <span
                      key={l}
                      className={
                        (i === 0 && order.payment_count > 0) ||
                        (i > 0 && order.state === "fulfilled")
                          ? "done"
                          : ""
                      }
                    >
                      <Check size={15} />
                      {l}
                    </span>
                  ))}
                </div>
                <div className="actions">
                  <button
                  disabled={busy || order.payment_count > 0 || order.payment_mode === "bridge_sandbox"}
                    onClick={() =>
                      action(async () => {
                        await api("/demo/orders/" + selected + "/pay", "POST");
                        setNotice("Paiement local simulé confirmé.");
                      })
                    }
                  >
                    Simuler le paiement
                  </button>
                  <button
                    disabled={busy || order.state !== "awaiting_resume"}
                    onClick={() =>
                      action(async () => {
                        await api(
                          "/demo/orders/" + selected + "/continue",
                          "POST",
                        );
                        setNotice("Signal de reprise envoyé à Temporal.");
                      })
                    }
                  >
                    Reprendre le chargement
                  </button>
                </div>
                <p className="small muted">
                  Paiements de test comptabilisés : {order.payment_count} ·{" "}
                  {order.card
                    ? "Carte simulée : " + order.card.load_count + " chargement"
                    : "Chargement non confirmé"}
                </p>
                {order.payment_mode === "bridge_sandbox" && (
                  <div className="actions">
                    <button
                      disabled={busy || order.payment_count > 0}
                      onClick={() =>
                        action(async () => {
                          const bank = await api(
                            "/orders/" + selected + "/bridge",
                            "POST",
                            {},
                          );
                          setNotice(
                            "Demande sandbox créée. Ouvrez le parcours bancaire avec le lien ci-dessous.",
                          );
                          setOrders(
                            orders.map((o) =>
                              o.id === selected ? { ...o, bridge: bank } : o,
                            ),
                          );
                        })
                      }
                    >
                      Créer le paiement Bridge
                    </button>
                    {order.bridge?.url && (
                      <a
                        href={order.bridge.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Ouvrir Demo Bank ↗
                      </a>
                    )}
                    <button
                      disabled={busy}
                      onClick={() =>
                        action(async () => {
                          const s = await api(
                            "/orders/" + selected + "/bridge/status",
                            "POST",
                            {},
                          );
                          setNotice("Statut bancaire : " + s.provider_status);
                        })
                      }
                    >
                      Vérifier le règlement
                    </button>
                  </div>
                )}
                {view === "console" && (
                  <div className="actions">
                    <button
                      disabled={busy || order.state !== "fulfilled"}
                      onClick={() =>
                        action(() =>
                          event("maas.validation.accepted.v1", "passage-1"),
                        )
                      }
                    >
                      Validation X / doublon
                    </button>
                    <button
                      disabled={busy || order.state !== "fulfilled"}
                      onClick={() =>
                        action(async () => {
                          await api("/proofs/" + selected, "POST", {});
                          setNotice(
                            "Lot signé ; ancrage blockchain demandé à Temporal.",
                          );
                        })
                      }
                    >
                      Ancrer les validations
                    </button>
                  </div>
                )}
                {order.state === "fulfilled" && order.quote.lines.some((l: Data) => ["bike", "parking"].includes(l.product)) && (
                  <PartnerPanel key={identity + "-" + order.id} api={api} order={order} aiEnabled={provider !== "disabled"} />
                )}
                {statement && (
                  <div className="statement">
                    <h3>Relevé de démonstration</h3>
                    <div>
                      <span>
                        Net prépayé {money(statement.net_prepaid_cents)}
                      </span>
                      <span>
                        Commission {money(statement.seller_commission_cents)}
                      </span>
                      <span>
                        Part opérateurs {money(statement.operators_cents)}
                      </span>
                      <span>
                        Vélo à facturer {money(statement.bike_due_cents)}
                      </span>
                    </div>
                    <p className="small muted">{statement.note}</p>
                    {statement.parking_adjustment_available_cents > 0 && (
                      <p>
                        Réduction P+R à examiner au SAV :{" "}
                        {money(statement.parking_adjustment_available_cents)}
                      </p>
                    )}
                  </div>
                )}
                {view === "sav" && (
                  <div className="refund">
                    <h3>Régularisation contrôlée par OPA</h3>
                    <label>
                      Montant en euros{" "}
                      <input
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={refund}
                        onChange={(e) => setRefund(e.target.value)}
                      />
                    </label>
                    <button
                      disabled={busy}
                      onClick={() =>
                        action(async () => {
                          await api(
                            "/orders/" + selected + "/refunds",
                            "POST",
                            {
                              amount_cents: Math.round(Number(refund) * 100),
                              reason:
                                "Régularisation de démonstration confirmée au guichet",
                              idempotency_key:
                                "sav-" +
                                selected +
                                "-" +
                                Math.round(Number(refund) * 100),
                            },
                          );
                          setNotice(
                            "Régularisation simulée enregistrée. Répéter la même demande ne la double pas.",
                          );
                        })
                      }
                    >
                      Confirmer la régularisation simulée
                    </button>
                    <p className="small muted">
                      Le conseiller est limité à 5 €. Un refus ne modifie aucun
                      montant. Aucun remboursement bancaire réel.
                    </p>
                  </div>
                )}
              </div>
            )}
          </section>
          <section className="card knowledge">
            <div className="card-heading">
              <Search size={19} />
              <h2>Comprendre les règles</h2>
              <span className="badge light">FalkorDB · sources fictives</span>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                action(async () => {
                  const r = await api("/knowledge/search", "POST", { query });
                  setSources(r.sources);
                  setNotice(r.note);
                });
              }}
            >
              <input
                aria-label="Question sur les règles"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <button disabled={busy}>Rechercher</button>
            </form>
            {sources.map((s) => (
              <article key={s.id}>
                <strong>{s.title}</strong>
                <p>{s.text}</p>
                <small>Source : {s.id}</small>
              </article>
            ))}
          </section>
          {view === "console" && (
            <section className="card">
              <div className="card-heading">
                <ShieldCheck size={19} />
                <h2>Intégrations : ce qui s’exécute</h2>
              </div>
              <div className="integration-grid">
                {integrations.map((i) => (
                  <div key={i.name}>
                    <span
                      className={
                        "badge " + (i.mode === "real" ? "real" : "light")
                      }
                    >
                      {i.mode === "real"
                        ? "Logiciel réel"
                        : i.mode === "simulated"
                          ? "Simulé"
                          : i.mode === "pending"
                            ? "À intégrer"
                            : i.mode === "configured"
                              ? "Activé"
                              : i.mode === "lab"
                                ? "Laboratoire séparé"
                                : "Non activé"}
                    </span>
                    <h3>{i.name}</h3>
                    <p className="small muted">{i.detail}</p>
                  </div>
                ))}
              </div>
              <div className="actions">
                <a
                  href="http://127.0.0.1:8088"
                  target="_blank"
                  rel="noreferrer"
                >
                  Temporal ↗
                </a>
                <a
                  href="http://127.0.0.1:16686"
                  target="_blank"
                  rel="noreferrer"
                >
                  Jaeger ↗
                </a>
              </div>
              <h3>Preuves de validation</h3>
              {proofs.length === 0 ? (
                <p className="muted">Aucun lot ancré pour le moment.</p>
              ) : (
                proofs.map((p) => (
                  <article className="proof" key={p.id}>
                    <strong>
                      {p.status === "anchored"
                        ? p.previous_chains?.length ? "Ré-ancré après remise à zéro locale" : "Ancré sur Anvil"
                        : p.status === "chain_reset" ? "Ancienne chaîne locale · réancrage nécessaire" : "En attente de Temporal"}
                    </strong>
                    <p>
                      SHA-256 : <code>{p.digest}</code>
                    </p>
                    <p className="small muted">
                      {p.chain
                        ? "Bloc " +
                          p.chain.block +
                          " · chaîne " +
                          p.chain.chain_id
                        : "Le parcours métier continue pendant l’ancrage."}{" "}
                      · Manifeste signé Ed25519
                    </p>
                    {p.chain && <p className="small muted">{p.chain.anchored_at ? <>Ancrage le <time dateTime={p.chain.anchored_at}>{new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "medium", timeZone: "Europe/Paris" }).format(new Date(p.chain.anchored_at))}</time> · heure de Paris</> : "Date d’ancrage indisponible"}</p>}
                    {p.chain?.instance_id && <p className="small muted">Instance locale : <code>{p.chain.instance_id}</code></p>}
                  </article>
                ))
              )}
            </section>
          )}
          {["sav", "console"].includes(view) && (
            <section className="card">
              <div className="card-heading">
                <Clock size={19} />
                <h2>Journal des opérations</h2>
              </div>
              <div className="timeline">
                {audit.slice(0, 25).map((a) => (
                  <div key={a.id}>
                    <span className="timeline-dot" />
                    <time>{new Date(a.at).toLocaleTimeString("fr-FR")}</time>
                    <strong>{a.action}</strong>
                    <small>{a.order_id?.slice(-12) || a.principal || ""}</small>
                  </div>
                ))}
              </div>
            </section>
          )}
          <footer>
            <span>ALIZÉ LAB · BILLETTIQUE AGENTIQUE</span>
            <span>
              Parcours fictifs · Aucune information voyageurs ni calcul
              d’itinéraire
            </span>
          </footer>
        </div>}
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
