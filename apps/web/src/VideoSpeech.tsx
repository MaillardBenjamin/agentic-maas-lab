import { useEffect, useRef, useState } from "react";
import { Camera, Check, LoaderCircle, Mic, Square, Video, Volume2, X } from "lucide-react";
import { LiveAudio, type LiveAudioState } from "./live-audio";
import { acquireWebcam, recordWebcamPhrase } from "./webcam-capture";
import "./video-speech.css";

type API = (path: string, method?: string, body?: Record<string, any> | Blob) => Promise<any>;
export function VideoSpeech({ api, onText, onAsk }: { api: API; onText: (text: string) => void; onAsk: (question: string) => Promise<string> }) {
  const [opened, setOpened] = useState(false), [status, setStatus] = useState<any>(null), [cloud, setCloud] = useState<any>(null);
  const [mode, setMode] = useState("avsr"), [language, setLanguage] = useState("fr");
  const [camera, setCamera] = useState(false), [starting, setStarting] = useState(false), [recording, setRecording] = useState(false), [seconds, setSeconds] = useState(0);
  const [wantAudio, setWantAudio] = useState(false), [localConsent, setLocalConsent] = useState(false), [liveState, setLiveState] = useState<LiveAudioState>("closed");
  const [caption, setCaption] = useState(""), [soundBlocked, setSoundBlocked] = useState(false);
  const [job, setJob] = useState<any>(null), [text, setText] = useState(""), [reviewed, setReviewed] = useState(false), [busy, setBusy] = useState(false);
  const [error, setError] = useState(""), [audioError, setAudioError] = useState(""), [notice, setNotice] = useState("");
  const video = useRef<HTMLVideoElement>(null), stream = useRef<MediaStream | null>(null), recorder = useRef<MediaRecorder | null>(null), live = useRef<LiveAudio | null>(null);
  const cancelPhrase = useRef<(() => void) | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null), deadline = useRef<ReturnType<typeof setTimeout> | null>(null);
  const active = useRef(true), revision = useRef(0), jobId = useRef("");
  const apiRef = useRef(api); apiRef.current = api;
  const frozen = starting || camera || recording || busy;

  function stopRecording() {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    if (recorder.current?.state === "recording") recorder.current.stop();
    if (active.current) setRecording(false);
  }
  function stopAll(erase = false) {
    revision.current++;
    cancelPhrase.current?.(); cancelPhrase.current = null;
    stopRecording();
    if (deadline.current) clearTimeout(deadline.current);
    deadline.current = null;
    live.current?.close(); live.current = null;
    stream.current?.getTracks().forEach(track => track.stop()); stream.current = null;
    if (video.current) video.current.srcObject = null;
    const id = jobId.current; jobId.current = "";
    if (id) apiRef.current("/perception/jobs/" + id, "DELETE").catch(() => {});
    if (active.current) {
      setCamera(false); setStarting(false); setBusy(false); setLiveState("closed"); setSoundBlocked(false);
      if (erase) { setJob(null); setText(""); setReviewed(false); setCaption(""); setLocalConsent(false); setNotice(""); setError(""); setAudioError(""); }
      else if (id) setJob((previous: any) => previous?.status === "completed" ? previous : null);
    }
  }
  useEffect(() => {
    const hidden = () => { if (document.hidden) stopAll(); };
    document.addEventListener("visibilitychange", hidden);
    return () => { active.current = false; document.removeEventListener("visibilitychange", hidden); stopAll(); };
  }, []);
  useEffect(() => {
    if (!opened) return;
    let valid = true;
    api("/perception/status").then(value => { if (valid) setStatus(value); }).catch(() => { if (valid) setStatus({ready: false, reason: "Moteur labial local indisponible."}); });
    api("/voice/status").then(value => { if (valid) setCloud(value); }).catch(() => { if (valid) setCloud({configured: false, reason: "Audio OpenAI indisponible."}); });
    return () => { valid = false; };
  }, [opened]);
  useEffect(() => {
    if (camera && video.current && stream.current) { video.current.srcObject = stream.current; video.current.play().catch(() => {}); }
  }, [camera]);
  useEffect(() => {
    if (!job?.id || !["queued", "processing"].includes(job.status)) return;
    let valid = true, timeout: ReturnType<typeof setTimeout>;
    const version = revision.current;
    async function poll() {
      try {
        const next = await apiRef.current("/perception/jobs/" + job.id);
        if (!valid || version !== revision.current) return;
        setJob(next);
        if (next.status === "completed") {
          setText(next.result.text || ""); setReviewed(false); setBusy(false);
          if (next.result.abstained) setError("Aucun texte exploitable. Recommencez face caméra ou écrivez votre demande.");
          return;
        }
        if (next.status === "failed") { setError(next.error); setBusy(false); return; }
        timeout = setTimeout(poll, 1500);
      } catch (e) { if (valid && version === revision.current) { setError((e as Error).message); setBusy(false); } }
    }
    timeout = setTimeout(poll, 1000);
    return () => { valid = false; clearTimeout(timeout); };
  }, [job?.id, job?.status]);

  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) { setError("La webcam n’est pas disponible dans ce navigateur. Ouvrez ce site en HTTPS ou sur localhost avec un navigateur compatible."); return; }
    const version = ++revision.current;
    setStarting(true); setError(""); setAudioError(""); setNotice(""); setCaption("");
    try {
      const media = await acquireWebcam(mode === "avsr" || wantAudio, () => active.current && version === revision.current);
      if (!media) return;
      stream.current = media; setCamera(true); setStarting(false);
      media.getVideoTracks().forEach(track => { track.onended = () => { if (version === revision.current) stopAll(); }; });
      deadline.current = setTimeout(() => { stopAll(); if (active.current) setNotice("Webcam et audio arrêtés après trois minutes. Le texte proposé reste disponible."); }, 180000);
      if (wantAudio) {
        const connection = new LiveAudio({api: apiRef.current, stream: media, ask: onAsk,
          state: value => { if (active.current && version === revision.current) setLiveState(value); },
          caption: value => { if (active.current && version === revision.current) setCaption(value); },
          fault: message => { if (active.current && version === revision.current) { setAudioError(message); if (mode === "vsr") media.getAudioTracks().forEach(track => track.stop()); } },
          expired: () => { if (version === revision.current) { stopAll(); setNotice("Session audio terminée après trois minutes."); } },
          soundBlocked: () => { if (active.current && version === revision.current) setSoundBlocked(true); },
        });
        live.current = connection; await connection.open();
      }
    } catch { if (active.current && version === revision.current) { stopAll(); setError("Accès à la webcam ou au micro refusé ou indisponible. Autorisez les appareils dans le navigateur puis réessayez."); } }
    finally { if (active.current && version === revision.current) setStarting(false); }
  }
  async function submit(blob: Blob, version: number) {
    if (!blob.size || blob.size > 20 * 1024 * 1024) { setError("Capture vide ou trop volumineuse. Recommencez avec une phrase plus courte."); setBusy(false); return; }
    try {
      const value = await apiRef.current(`/perception/jobs?mode=${mode}&framing=face&language=${language}`, "POST", blob);
      if (!active.current || version !== revision.current) { if (value.id) apiRef.current("/perception/jobs/" + value.id, "DELETE").catch(() => {}); return; }
      jobId.current = value.id; setJob(value);
    } catch (e) { if (active.current && version === revision.current) { setError((e as Error).message); setBusy(false); } }
  }
  function capturePhrase() {
    if (!stream.current || !localConsent || busy || recording || !status?.ready) return;
    if (typeof MediaRecorder === "undefined") { setError("Ce navigateur ne permet pas l’analyse locale de la webcam. Essayez un navigateur compatible, ou utilisez la saisie écrite."); return; }
    if (jobId.current) apiRef.current("/perception/jobs/" + jobId.current, "DELETE").catch(() => {});
    jobId.current = ""; setJob(null); setText(""); setReviewed(false); setError(""); setNotice(""); setBusy(true);
    const version = revision.current;
    try {
      const phrase = recordWebcamPhrase(stream.current, mode === "vsr");
      cancelPhrase.current = phrase.cancel;
      recorder.current = phrase.recorder;
      phrase.result.then(blob => {
        if (!active.current || version !== revision.current) return;
        cancelPhrase.current = null;
        if (timer.current) clearInterval(timer.current); timer.current = null;
        setRecording(false); submit(blob, version);
      }).catch(error => {
        if (!active.current || version !== revision.current) return;
        cancelPhrase.current = null;
        if (timer.current) clearInterval(timer.current); timer.current = null;
        setRecording(false); setBusy(false); setError(error.message);
      });
      setRecording(true); setSeconds(0);
      const began = Date.now();
      timer.current = setInterval(() => { const elapsed = Math.floor((Date.now() - began) / 1000); setSeconds(elapsed); if (elapsed >= 8) stopRecording(); }, 250);
    } catch { setBusy(false); setError("Impossible de capturer cette webcam. Essayez un autre navigateur."); }
  }
  const liveLabel = {connecting: "Connexion audio OpenAI…", listening: "Audio OpenAI en direct · à votre écoute", speaking: "Réponse audio OpenAI en cours", consulting: "Consultation des agents métier…", closed: "Audio OpenAI arrêté"}[liveState];
  return <div className="video-speech">
    <button type="button" className="video-speech-toggle" aria-expanded={opened} onClick={() => { if (opened) stopAll(true); setOpened(!opened); }}><Camera size={18} /> Webcam et reconnaissance labiale</button>
    {opened && <div className="video-speech-body">
      <h3>Parler face à la webcam</h3>
      <p>Gardez le visage bien éclairé et regardez la caméra. La vidéo est traitée sur ce Mac. L’audio OpenAI est une aide facultative, activée séparément.</p>
      <div className="video-speech-options">
        <label>Reconnaissance locale<select value={mode} disabled={frozen} onChange={e => setMode(e.target.value)}><option value="avsr">Audio + lèvres, en local</option><option value="vsr">Lèvres seules, en local</option></select></label>
        <label>Langue de la phrase<select value={language} disabled={frozen} onChange={e => setLanguage(e.target.value)}><option value="fr">Français</option><option value="en">Anglais</option><option value="es">Espagnol</option><option value="de">Allemand</option><option value="it">Italien</option><option value="pt">Portugais</option><option value="el">Grec</option><option value="ru">Russe</option><option value="ar">Arabe</option></select></label>
      </div>
      <p className="small muted">{status?.ready ? "Moteur labial local disponible · courtes phrases, analyse différée." : status?.reason || "Vérification du moteur local…"}</p>
      <label className="check"><input type="checkbox" checked={wantAudio} disabled={frozen || !cloud?.configured} onChange={e => setWantAudio(e.target.checked)} />Ajouter l’audio OpenAI en direct : j’autorise l’envoi du son et des textes de cette conversation à OpenAI.</label>
      <p className="small muted">{cloud?.configured ? "OpenAI reçoit l’audio et les textes de dialogue. Les images de la webcam restent sur ce Mac." : cloud?.reason || "Vérification de l’audio facultatif…"}</p>
      {!camera ? <button type="button" className="video-speech-analyze" disabled={starting} onClick={startCamera}><Camera size={17} />{starting ? "Autorisation des appareils…" : wantAudio ? "Démarrer la webcam et l’audio" : "Démarrer la webcam"}</button> : <>
        <div className="video-speech-preview"><video ref={video} autoPlay muted playsInline aria-label="Aperçu de la webcam" />{recording && <span role="status">Capture de la phrase : {seconds} / 8 s</span>}</div>
        <label className="check"><input type="checkbox" checked={localConsent} disabled={busy || recording} onChange={e => setLocalConsent(e.target.checked)} />J’autorise l’analyse locale d’une courte capture webcam. Les images sont effacées côté moteur après le traitement.</label>
        {recording ? <button type="button" className="video-speech-stop" onClick={stopRecording}><Square size={15} />Terminer la phrase et analyser</button> : <button type="button" className="video-speech-analyze" disabled={!localConsent || busy || !status?.ready} onClick={capturePhrase}><Video size={16} />{busy ? "Analyse locale en cours…" : "Analyser une phrase · 8 secondes"}</button>}
        <button type="button" className="video-speech-clear" onClick={() => stopAll()}><Square size={15} />Arrêter la webcam et l’audio</button>
      </>}
      {starting && <button type="button" className="video-speech-clear" onClick={() => stopAll()}>Annuler l’ouverture des appareils</button>}
      {busy && !recording && <p role="status"><LoaderCircle className="video-speech-spin" size={16} />Lecture locale en cours. Le calcul peut prendre plusieurs dizaines de secondes.</p>}
      {wantAudio && camera && <div className="video-speech-live"><p role="status"><Mic size={16} />{liveLabel}</p>{caption && <p className="video-speech-caption">{caption}</p>}{soundBlocked && <button type="button" onClick={() => { live.current?.play(); setSoundBlocked(false); }}><Volume2 size={15} />Activer le son des réponses</button>}</div>}
      {(text || job?.status === "completed") && <div className="video-speech-result"><label>Texte de la demande — à vérifier<textarea rows={3} maxLength={2000} value={text} onChange={e => { setText(e.target.value); setReviewed(false); }} /></label><p className="small muted">{job?.result?.audio_used ? "Audio et lèvres utilisés localement" : "Lèvres seules analysées localement"}. Résultat expérimental : corrigez les mots nécessaires.</p><label className="check"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />J’ai relu et validé ce texte.</label><button type="button" className="video-speech-analyze" disabled={!reviewed || !text.trim()} onClick={() => { onText(text.trim()); setNotice("Texte placé dans votre message. Vous pouvez encore le modifier avant de l’envoyer."); }}><Check size={15} />Utiliser dans mon message</button>{camera && wantAudio && liveState !== "closed" && <button type="button" className="video-speech-analyze" disabled={!reviewed || !text.trim() || liveState !== "listening"} onClick={() => { if (live.current?.shareReviewedText(text)) setNotice("Texte validé transmis à la conversation audio. Aucune image envoyée à OpenAI."); }}>Dire cette demande à l’assistant audio</button>}</div>}
      {(text || job) && <button type="button" className="video-speech-clear" onClick={() => stopAll(true)}><X size={15} />Effacer la capture et le texte</button>}
      {error && <p role="alert" className="alert error">{error}</p>}{audioError && <p role="alert" className="alert error">{audioError}</p>}{notice && <p role="status" className="alert success">{notice}</p>}
    </div>}
  </div>;
}
