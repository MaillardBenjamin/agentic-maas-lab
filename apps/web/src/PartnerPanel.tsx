import { useEffect, useRef, useState } from "react";
import { Bike, CarFront } from "lucide-react";

type Data = Record<string, any>;
type API = (path: string, method?: string, body?: Data) => Promise<any>;
const states: Record<string, string> = { available: "À réserver", reserved: "Réservé", active: "Usage en cours", completed: "Usage terminé", cancelled: "Réservation annulée" };
const actions: Record<string, Record<string, string>> = {
  bike: { reserve: "Réserver un vélo via A2A", start: "Démarrer la location via A2A", finish: "Restituer le vélo · 10 min via A2A", cancel: "Annuler la réservation via A2A" },
  parking: { reserve: "Réserver une place via A2A", start: "Entrer au parking via A2A", finish: "Sortir du parking via A2A", cancel: "Annuler la réservation via A2A" },
};

export function PartnerPanel({ api, order, aiEnabled }: { api: API; order: Data; aiEnabled: boolean }) {
  const [data, setData] = useState<Data | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fetchError, setFetchError] = useState("");
  const keys = useRef(new Map<string, string>());
  useEffect(() => {
    let live = true;
    async function refresh() {
      try {
        const value = await api("/orders/" + order.id + "/partners");
        if (live) { setData(value); setFetchError(""); }
      } catch (e) {
        if (live) setFetchError((e as Error).message);
      }
    }
    refresh();
    const timer = setInterval(refresh, 2500);
    return () => { live = false; clearInterval(timer); };
  }, [order.id]);
  const pending = data?.operations.some((o: Data) => ["queued", "running", "executed"].includes(o.status));
  async function act(partner: string, action: string, booking: Data | undefined) {
    setBusy(true); setError("");
    const signature = [partner, action, booking?.generation || 0, booking?.state || "available"].join(":");
    if (!keys.current.has(signature)) keys.current.set(signature, "partner-ui-" + crypto.randomUUID());
    try {
      await api("/orders/" + order.id + "/partner-operations", "POST", {
        partner, action, confirmed: true, idempotency_key: keys.current.get(signature),
        ...(partner === "bike" && action === "finish" ? { duration_seconds: 600 } : {}),
      });
      setConfirmed(false);
      setData(await api("/orders/" + order.id + "/partners"));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function resume(id: string) {
    setBusy(true); setError("");
    try {
      await api("/partner-operations/" + id + "/resume", "POST", { confirmed: true });
      setConfirmed(false);
      setData(await api("/orders/" + order.id + "/partners"));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const products = order.quote.lines.map((l: Data) => l.product);
  return (
    <section className="partner-panel" aria-label="Coopération A2A avec les partenaires">
      <h3>Utiliser vos services avec les agents partenaires</h3>
      <p className="small muted">Agent MaaS → A2A → agent partenaire → MCP → service simulé. Les équipements restent fictifs ; chaque action est confirmée ci-dessous et suivie dans Temporal.</p>
      {!aiEnabled && <p className="small">Activer un fournisseur IA pour lancer ces échanges A2A.</p>}
      {data && <>
        <label className="check small">
          <input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} disabled={busy} />
          Je confirme l’action simulée choisie. La restitution vélo utilise une durée fictive de 10 minutes ; aucun débit bancaire n’est effectué.
        </label>
        <div className="partner-grid">
          {["bike", "parking"].filter(p => products.includes(p)).map(partner => {
            const booking = data.bookings.find((b: Data) => b.partner === partner);
            const latest = data.operations.find((o: Data) => o.partner === partner);
            const state = booking?.state || "available";
            const options = state === "available" || state === "cancelled" ? ["reserve"] : state === "reserved" ? ["start", "cancel"] : state === "active" ? ["finish"] : [];
            const failed = latest?.status === "failed";
            const Icon = partner === "bike" ? Bike : CarFront;
            return (
              <article className="partner-card" key={partner}>
                <h4><Icon size={18} />{partner === "bike" ? "Partenaire vélo" : "Partenaire parking"}<span className="badge light">Service simulé</span></h4>
                <p className="small"><strong>{states[state]}</strong> · {data.availability[partner]} ressource(s) disponible(s)</p>
                {booking?.asset_id && <p className="small muted">Ressource : {booking.asset_id}</p>}
                <div className="actions">
                  {!failed && options.map(action => <button key={action} disabled={!confirmed || busy || pending || !aiEnabled || (action === "reserve" && data.availability[partner] === 0)} onClick={() => act(partner, action, booking)}>{actions[partner][action]}</button>)}
                  {latest && latest.status !== "completed" && <button disabled={!confirmed || busy || !aiEnabled} onClick={() => resume(latest.id)}>{failed ? "Reprendre l’opération confirmée" : "Relancer le suivi Temporal"}</button>}
                </div>
                {latest && <div className="partner-receipt" aria-live="polite">
                  <span className={"badge " + (latest.status === "completed" ? "real" : "light")}>
                    {latest.status === "completed" ? "Parcours A2A/MCP vérifié" : failed ? "Opération interrompue ou refusée" : "En cours via Temporal"}
                  </span>
                  <p className="small muted">{latest.test_only ? "Test de protocole avec modèle déterministe, sans LLM" : latest.mode === "ollama_local" ? "Inférence locale Ollama · " + latest.model : latest.mode === "openai_via_agno" ? "Inférence OpenAI · " + latest.model : "Attente du résultat des agents"}</p>
                  {latest.evidence && <p className="small">Agents A2A : {latest.evidence.a2a_agents.join(" → ")}<br />Outils MCP exécutés : {latest.evidence.mcp_tools.join(", ")}</p>}
                  {latest.result && <p className="small">Effet métier enregistré : {latest.result.effect_count} · {states[latest.result.booking.state]}</p>}
                  {latest.result?.event_id && <p className="small muted">Événement CloudEvents enregistré ; relevé et commissions mis à jour.</p>}
                  {latest.error && <p className="small error partner-error">{latest.error}</p>}
                  {latest.explanation && <details><summary className="small">Réponse de l’agent</summary><p className="small partner-explanation">{latest.explanation}</p></details>}
                </div>}
              </article>
            );
          })}
        </div>
      </>}
      {(error || fetchError) && <p role="alert" className="alert error">{error || fetchError}</p>}
    </section>
  );
}
