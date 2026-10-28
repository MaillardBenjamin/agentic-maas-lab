import { useEffect, useRef, useState } from 'react';
import { Activity, ArrowRight, CheckCircle2, Circle, LoaderCircle, X, XCircle } from 'lucide-react';
import { actorLabels, actorState, mergeExchanges, type Exchange } from './agent-activity-state';
import './agent-activity.css';

type Data = Record<string, any>;
type API = (path: string, method?: string, body?: Data) => Promise<any>;
const phases: Record<string, string> = { started: 'En cours', running: 'En cours', completed: 'Terminé', failed: 'Échec', idle: 'Non sollicité' };
const modes: Record<string, string> = { ollama_local: 'Ollama local · modèle réel', openai_via_agno: 'OpenAI · modèle réel', 'fixture-no-llm': 'Test de protocole · modèle simulé' };
function StateIcon({ state }: { state: string }) {
  return state === 'started' || state === 'running' ? <LoaderCircle size={15} className="activity-spin" /> : state === 'completed' ? <CheckCircle2 size={15} /> : state === 'failed' ? <XCircle size={15} /> : <Circle size={15} />;
}

export function AgentActivity({ api }: { api: API }) {
  const [opened, setOpened] = useState(false);
  const [runs, setRuns] = useState<Data[]>([]);
  const [spans, setSpans] = useState<Exchange[]>([]);
  const [selected, setSelected] = useState('');
  const [connection, setConnection] = useState('connecting');
  const [truncated, setTruncated] = useState(false);
  const [updated, setUpdated] = useState('');
  const apiRef = useRef(api);
  apiRef.current = api;
  const cursor = useRef(0), generation = useRef('');
  useEffect(() => {
    const show = () => { setSelected(''); setOpened(true); };
    const keyboard = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpened(false); };
    window.addEventListener('maas-agent-activity-open', show);
    window.addEventListener('keydown', keyboard);
    return () => { window.removeEventListener('maas-agent-activity-open', show); window.removeEventListener('keydown', keyboard); };
  }, []);
  useEffect(() => {
    if (!opened) return;
    let live = true, timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const data = await apiRef.current('/agent-activity?after=' + cursor.current);
        if (!live) return;
        if (generation.current && generation.current !== data.generation) {
          // New API process: refetch from zero instead of hiding new lower cursors.
          generation.current = data.generation; cursor.current = 0; setSpans([]); setRuns([]); setSelected('');
          timer = setTimeout(poll, 0); return;
        }
        generation.current = data.generation; cursor.current = data.cursor;
        setSpans(previous => mergeExchanges(previous, data.events));
        setRuns(data.runs); setTruncated(data.truncated); setConnection('connected');
        setUpdated(new Date().toLocaleTimeString('fr-FR'));
      } catch { if (live) setConnection('disconnected'); }
      if (live) timer = setTimeout(poll, 800);
    }
    poll();
    return () => { live = false; clearTimeout(timer); };
  }, [opened]);
  const run = runs.find(value => value.id === selected) || runs.at(-1);
  const current = spans.filter(value => value.run_id === run?.id);
  const actors = ['conversation', 'tariffs', 'sav', 'clearing', 'mobility', 'transport', 'bike', 'parking'];
  return <div className="agent-activity">
    {!opened && <button className="activity-launch" type="button" onClick={() => setOpened(true)}><Activity size={18} /> Échanges en direct</button>}
    {opened && <section className="activity-panel" aria-label="Échanges entre agents en direct">
      <header className="activity-header"><div><span className="activity-eyebrow">DANS LES COULISSES</span><h2><Activity size={19} /> Échanges en direct</h2></div><button type="button" aria-label="Fermer les échanges en direct" onClick={() => setOpened(false)}><X size={20} /></button></header>
      <div className="activity-scroll">
        <p className={'activity-connection ' + connection}><span />{connection === 'connected' ? 'Flux connecté · actualisation toutes les 0,8 s' : connection === 'disconnected' ? 'Flux interrompu · reconnexion en cours' : 'Connexion au suivi…'}</p>
        <p className="activity-intro">Suivez les délégations entre agents et leurs appels aux outils pendant votre demande.</p>
        {runs.length > 0 && <label className="activity-select">Demande observée<select value={selected || ''} onChange={event => setSelected(event.target.value)}><option value="">Dernière demande</option>{[...runs].reverse().map(value => <option key={value.id} value={value.id}>{value.title} · {new Date(value.at).toLocaleTimeString('fr-FR')}</option>)}</select></label>}
        <div className="activity-actors">{actors.map(actor => { const state = actorState(current, actor); return <div className={'activity-actor ' + state} key={actor}><StateIcon state={state} /><strong>{actorLabels[actor]}</strong><small>{phases[state]}</small></div>; })}</div>
        {!run ? <p className="activity-empty">Aucun échange observé dans cette session. Posez une question à l’assistant ou confirmez une action vélo ou parking pour suivre le parcours.</p> : <>
          <div className="activity-run"><strong>{run.title}</strong><span className={'activity-phase ' + run.state}><StateIcon state={run.state} />{phases[run.state]}</span><small>{modes[run.mode] || 'Fournisseur non identifié'}</small></div>
          <ol className="activity-exchanges" aria-label="Chronologie des échanges">{current.map(span => <li key={span.span_id} className={span.state}><div className="activity-exchange-top"><span className="activity-protocol">{span.protocol}</span><span className={'activity-phase ' + span.state}><StateIcon state={span.state} />{phases[span.state]}</span></div><p><strong>{actorLabels[span.source] || span.source}</strong><ArrowRight size={15} /><strong>{actorLabels[span.target] || span.target}</strong></p><small>{span.protocol === 'A2A' ? 'Délégation à un agent' : 'Appel à un outil métier'}{span.target.startsWith('bike_') || span.target.startsWith('parking_') ? ' · service simulé' : ''} · {span.duration_ms === null ? 'Attente du retour' : (span.duration_ms / 1000).toLocaleString('fr-FR', {maximumFractionDigits: 2}) + ' s'}</small></li>)}</ol>
        </>}
        {truncated && <p className="activity-warning">Une partie de l’historique a expiré ou quitté le tampon.</p>}
        <p className="activity-footnote">Événements réellement observés · historique temporaire de 15 min. Aucun contenu de message affiché. {updated && <>Dernière lecture : {updated}.</>}</p>
      </div>
    </section>}
  </div>;
}
