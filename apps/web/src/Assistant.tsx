import { useState } from "react";
import type { AIProvider } from "./DemoScope";
import { VideoSpeech } from "./VideoSpeech";
type API = (
  path: string,
  method?: string,
  body?: Record<string, any> | Blob,
) => Promise<any>;

export function Assistant({
  api,
  agent = "conversation",
  orderId,
  runtimeProvider = "disabled",
  customer = false,
  advisor = false,
  travelerId,
  seller = "app",
  travelDate,
  onProposal,
}: {
  api: API;
  agent?: string;
  orderId?: string;
  runtimeProvider?: AIProvider;
  customer?: boolean;
  advisor?: boolean;
  travelerId?: string;
  seller?: "app" | "agency";
  travelDate?: string;
  onProposal?: (proposal: Record<string, any>) => void;
}) {
  const [message, setMessage] = useState(
      advisor ? "Quelles règles SAV vérifier avant une régularisation ?" : "Pourquoi le tarif étudiant est-il de 7 € ?",
    ),
    [answer, setAnswer] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [answerInfo, setAnswerInfo] = useState<any>(null);
  async function ask() {
    window.dispatchEvent(new Event('maas-agent-activity-open'));
    setBusy(true);
    setError("");
    try {
      const r = await api("/chat", "POST", {
        message,
        agent,
        order_id: orderId || undefined,
        traveler: travelerId,
        seller,
        travel_date: travelDate || undefined,
      });
      setAnswer(r.text);
      setAnswerInfo(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function consult(question: string): Promise<string> {
    window.dispatchEvent(new Event('maas-agent-activity-open'));
    const result = await api("/chat", "POST", {message: question, agent, order_id: orderId || undefined, traveler: travelerId, seller, travel_date: travelDate || undefined});
    setAnswer(result.text); setAnswerInfo(result);
    return result.text;
  }
  return (
    <section className="card">
      <div className="card-heading">
        <span className="number">IA</span>
        <h2>{advisor ? "Assistant du conseiller" : customer ? "Votre assistant Alizé" : "Dialoguer avec les agents"}</h2>
        {!customer && !advisor && <span className="badge light">Agno · A2A · MCP</span>}
      </div>
      <p className="small muted">
        {advisor ? "L’assistant consulte les organisations concernées pour expliquer le dossier ou préparer un devis. Vous vérifiez et confirmez les actions dans le poste." : customer ? "Demandez un tarif, une disponibilité ou une proposition avec les produits et la date. L’assistant consulte les organisations concernées ; vous examinez l’offre avant de confirmer." : <>{runtimeProvider === "ollama" ? "Modèle Ollama local actif. " : runtimeProvider === "openai" ? "Modèle OpenAI actif. " : "IA à activer dans la configuration. "}Les coordinateurs consultent les agents des organisations. Vous confirmez les propositions et opérations dans les écrans métier.</>}
      </p>
      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault();
          ask();
        }}
      >
        <input
          aria-label="Message aux agents"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          maxLength={2000}
        />
        <button disabled={busy || runtimeProvider === "disabled"}>{busy ? "Réponse en cours…" : "Envoyer"}</button>
      </form>
      <VideoSpeech api={api} onText={value => setMessage(value)} onAsk={consult} />
      {answer && (
        <article className="agent-answer">
          {!customer && !advisor && <small>{answerInfo?.mode === "ollama_local" ? "Réponse locale Ollama" : "Réponse OpenAI"} via Agno · {answerInfo?.model}</small>}
          <p style={{ whiteSpace: "pre-wrap" }}>{answer}</p>
          {answerInfo?.proposal && onProposal && <button type="button" onClick={() => onProposal(answerInfo.proposal)}>Examiner la proposition · {(answerInfo.proposal.total_cents / 100).toLocaleString("fr-FR", {style: "currency", currency: "EUR"})}</button>}
          {!customer && !advisor && answerInfo?.evidence?.mcp_tools?.length > 0 && <small>Outils MCP exécutés : {answerInfo.evidence.mcp_tools.join(", ")}{answerInfo.evidence.a2a_agents.length > 0 ? " · Délégation A2A : " + answerInfo.evidence.a2a_agents.join(", ") : ""}</small>}
        </article>
      )}
      {error && (
        <p role="alert" className="alert error">
          {error}
        </p>
      )}
    </section>
  );
}
