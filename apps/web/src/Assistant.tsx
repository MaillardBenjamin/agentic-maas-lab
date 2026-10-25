import { useEffect, useRef, useState } from "react";
import type { AIProvider } from "./DemoScope";
type API = (
  path: string,
  method?: string,
  body?: Record<string, any>,
) => Promise<any>;

export function Assistant({
  api,
  agent = "conversation",
  orderId,
  runtimeProvider = "disabled",
}: {
  api: API;
  agent?: string;
  orderId?: string;
  runtimeProvider?: AIProvider;
}) {
  const [message, setMessage] = useState(
      "Pourquoi le tarif étudiant est-il de 7 € ?",
    ),
    [answer, setAnswer] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [voice, setVoice] = useState(false),
    [caption, setCaption] = useState("");
  const [answerInfo, setAnswerInfo] = useState<any>(null);
  const rtc = useRef<RTCPeerConnection | null>(null),
    audio = useRef<HTMLAudioElement | null>(null),
    stream = useRef<MediaStream | null>(null),
    timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  function stop() {
    rtc.current?.close();
    rtc.current = null;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    if (timer.current) clearTimeout(timer.current);
    setVoice(false);
  }
  useEffect(() => () => stop(), []);
  async function ask() {
    setBusy(true);
    setError("");
    try {
      const r = await api("/chat", "POST", {
        message,
        agent,
        order_id: orderId || undefined,
      });
      setAnswer(r.text);
      setAnswerInfo(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function start() {
    setError("");
    setBusy(true);
    try {
      const integrations = await api("/integrations");
      if (
        !integrations.some(
          (i: any) => i.name === "OpenAI" && i.mode === "configured",
        )
      )
        throw new Error(
          "Voix cloud désactivée : nouvelle clé locale et activation IA requises.",
        );
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      const session = await api("/voice/session", "POST", {});
      const pc = new RTCPeerConnection();
      rtc.current = pc;
      audio.current = new Audio();
      audio.current.autoplay = true;
      pc.ontrack = (e) => {
        if (audio.current) audio.current.srcObject = e.streams[0];
      };
      stream.current
        .getTracks()
        .forEach((t) => pc.addTrack(t, stream.current!));
      const dc = pc.createDataChannel("oai-events");
      dc.onmessage = async (e) => {
        const event = JSON.parse(e.data);
        if (event.type === "response.output_audio_transcript.delta")
          setCaption((c) => c + event.delta);
        if (event.type === "response.created") setCaption("");
        if (
          event.type === "response.function_call_arguments.done" &&
          event.name === "ask_ticketing_agent"
        ) {
          let result = "Service métier indisponible.";
          try {
            const args = JSON.parse(event.arguments);
            result = (
              await api("/chat", "POST", {
                message: args.question,
                agent: "conversation",
                order_id: orderId || undefined,
              })
            ).text;
          } catch (e) {
            setError((e as Error).message);
          }
          if (dc.readyState === "open") {
            dc.send(
              JSON.stringify({
                type: "conversation.item.create",
                item: {
                  type: "function_call_output",
                  call_id: event.call_id,
                  output: result,
                },
              }),
            );
            dc.send(JSON.stringify({ type: "response.create" }));
          }
        }
      };
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      const response = await fetch("https://api.openai.com/v1/realtime/calls", {
        method: "POST",
        headers: {
          Authorization: "Bearer " + session.value,
          "Content-Type": "application/sdp",
        },
        body: offer.sdp,
      });
      if (!response.ok) throw new Error("Connexion vocale refusée par OpenAI.");
      await pc.setRemoteDescription({
        type: "answer",
        sdp: await response.text(),
      });
      pc.onconnectionstatechange = () => {
        if (["failed", "closed", "disconnected"].includes(pc.connectionState))
          stop();
      };
      setVoice(true);
      timer.current = setTimeout(stop, 180000);
    } catch (e) {
      setError((e as Error).message);
      stop();
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card">
      <div className="card-heading">
        <span className="number">IA</span>
        <h2>Dialoguer avec les agents</h2>
        <span className="badge light">Agno · A2A · MCP</span>
      </div>
      <p className="small muted">
        {runtimeProvider === "ollama" ? "Modèle Ollama local actif. " : runtimeProvider === "openai" ? "Modèle OpenAI actif. " : "IA à activer dans la configuration. "}
        Les agents expliquent les offres et consultent les dossiers. La préparation du panier depuis le dialogue reste à réaliser ; vous confirmez les opérations dans les écrans métier.
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
        <button disabled={busy}>Envoyer</button>
      </form>
      <div className="actions">
        <button disabled={busy || runtimeProvider !== "openai"} onClick={() => (voice ? stop() : start())}>
          {voice ? "Arrêter le micro" : "Démarrer la voix OpenAI"}
        </button>
        <span className="small muted">
          {voice
            ? "Micro actif · arrêt au bout de 3 minutes"
            : runtimeProvider === "ollama" ? "Voix expérimentale en mode OpenAI ; texte traité sur le Mac" : "Voix expérimentale · audio et latence à valider"}
        </span>
      </div>
      {caption && <p aria-live="polite">{caption}</p>}
      {answer && (
        <article className="agent-answer">
          <small>{answerInfo?.mode === "ollama_local" ? "Réponse locale Ollama" : "Réponse OpenAI"} via Agno · {answerInfo?.model}</small>
          <p style={{ whiteSpace: "pre-wrap" }}>{answer}</p>
          {answerInfo?.evidence?.mcp_tools?.length > 0 && <small>Outils MCP exécutés : {answerInfo.evidence.mcp_tools.join(", ")}{answerInfo.evidence.a2a_agents.length > 0 ? " · Délégation A2A : " + answerInfo.evidence.a2a_agents.join(", ") : ""}</small>}
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
