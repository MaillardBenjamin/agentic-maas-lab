export type LiveAudioState = 'connecting' | 'listening' | 'speaking' | 'consulting' | 'closed';
type Options = {
  api: (path: string, method?: string, body?: Record<string, any>) => Promise<any>;
  stream: MediaStream;
  ask: (question: string) => Promise<string>;
  state: (state: LiveAudioState) => void;
  caption: (text: string) => void;
  fault: (message: string) => void;
  expired: () => void;
  soundBlocked: () => void;
};
type Runtime = { peer: () => RTCPeerConnection; audio: () => HTMLAudioElement; fetch: typeof fetch };

/** Owns audio transport only. Camera/video tracks never enter the peer connection. */
export class LiveAudio {
  options: Options;
  runtime: Runtime;
  pc: RTCPeerConnection | null = null;
  dc: RTCDataChannel | null = null;
  speaker: HTMLAudioElement | null = null;
  closed = false;
  responding = false;
  pendingTools = 0;
  seenCalls = new Set<string>();
  toolOutputs: Record<string, any>[] = [];
  responseText = '';
  timeout: ReturnType<typeof setTimeout> | null = null;
  deadline: ReturnType<typeof setTimeout> | null = null;
  abort = new AbortController();

  constructor(options: Options, runtime?: Partial<Runtime>) {
    this.options = options;
    this.runtime = {peer: () => new RTCPeerConnection(), audio: () => new Audio(), fetch: (...args) => fetch(...args), ...runtime};
  }
  get canSend(): boolean { return !this.closed && this.dc?.readyState === 'open' && !this.responding && !this.pendingTools; }
  notify() { if (!this.closed) this.options.state(this.pendingTools ? 'consulting' : this.responding ? 'speaking' : 'listening'); }
  send(event: Record<string, any>) { if (!this.closed && this.dc?.readyState === 'open') this.dc.send(JSON.stringify(event)); }
  async open() {
    if (!this.options.stream.getAudioTracks().length) throw new Error('Un microphone est requis pour l’audio OpenAI.');
    this.options.state('connecting');
    this.timeout = setTimeout(() => this.fail('La connexion audio a dépassé le délai prévu.'), 30000);
    try {
      const session = await this.options.api('/voice/session', 'POST', {consent: true});
      if (this.closed) return;
      if (!session.audio_only || session.video_sent_to_openai !== false) throw new Error('Configuration audio invalide.');
      const pc = this.runtime.peer(); this.pc = pc;
      const audio = this.runtime.audio(); this.speaker = audio; audio.autoplay = true;
      pc.ontrack = event => { if (!this.closed && event.streams[0]) { audio.srcObject = event.streams[0]; this.play(); } };
      for (const track of this.options.stream.getAudioTracks()) pc.addTrack(track, this.options.stream);
      const dc = pc.createDataChannel('oai-events'); this.dc = dc;
      dc.onopen = () => {
        if (this.closed) return;
        if (this.timeout) clearTimeout(this.timeout);
        this.timeout = null;
        this.deadline = setTimeout(() => { this.close(); this.options.expired(); }, Math.min(180, session.client_duration_limit_seconds || 180) * 1000);
        this.notify();
      };
      dc.onmessage = event => { try { const value = JSON.parse(event.data); this.receive(value); } catch { /* Ignore malformed metadata, never execute it. */ } };
      dc.onclose = () => { if (!this.closed) this.fail('La connexion audio a été fermée.'); };
      pc.onconnectionstatechange = () => { if (!this.closed && ['failed', 'disconnected', 'closed'].includes(pc.connectionState)) this.fail('La connexion audio a été interrompue.'); };
      const offer = await pc.createOffer(); if (this.closed) return;
      await pc.setLocalDescription(offer); if (this.closed) return;
      const response = await this.runtime.fetch('https://api.openai.com/v1/realtime/calls', {method: 'POST', headers: {Authorization: 'Bearer ' + session.value, 'Content-Type': 'application/sdp'}, body: offer.sdp, signal: this.abort.signal});
      if (!response.ok) throw new Error('OpenAI a refusé la connexion audio.');
      const sdp = await response.text(); if (this.closed) return;
      await pc.setRemoteDescription({type: 'answer', sdp});
    } catch (error) { if (!this.closed) this.fail((error as Error).message || 'Audio OpenAI indisponible.'); }
  }
  async play() { try { await this.speaker?.play(); } catch { if (!this.closed) this.options.soundBlocked(); } }
  receive(event: Record<string, any>) {
    if (this.closed) return;
    if (event.type === 'response.created') { this.responding = true; this.responseText = ''; this.options.caption(''); this.notify(); }
    if (['response.output_audio_transcript.delta', 'response.output_text.delta'].includes(event.type)) {
      this.responseText = (this.responseText + (typeof event.delta === 'string' ? event.delta : '')).slice(-6000); this.options.caption(this.responseText);
    }
    if (event.type === 'response.done') { this.responding = false; this.flush(); this.notify(); }
    if (event.type === 'error') this.fail('Le service audio a signalé une erreur. Vous pouvez poursuivre en local.');
    if (event.type === 'response.function_call_arguments.done') this.call(event);
  }
  async call(event: Record<string, any>) {
    if (event.name !== 'ask_ticketing_agent' || typeof event.call_id !== 'string' || this.seenCalls.has(event.call_id) || this.seenCalls.size >= 64) return;
    this.seenCalls.add(event.call_id);
    this.pendingTools++; this.notify();
    let text = 'Demande non prise en charge. Aucune opération métier exécutée.';
    try {
      const args = JSON.parse(event.arguments);
      if (typeof args.question === 'string' && args.question.trim() && args.question.length <= 2000 && Object.keys(args).every(key => key === 'question')) text = (await this.options.ask(args.question)).slice(0, 12000);
    } catch { text = 'La consultation métier n’a pas abouti. Aucun succès ne peut être confirmé.'; }
    if (this.closed) return;
    this.pendingTools--;
    this.toolOutputs.push({type: 'conversation.item.create', item: {type: 'function_call_output', call_id: event.call_id, output: text}});
    this.flush(); this.notify();
  }
  flush() {
    if (!this.canSend || !this.toolOutputs.length) return;
    for (const event of this.toolOutputs.splice(0)) this.send(event);
    this.send({type: 'response.create'}); this.responding = true;
  }
  shareReviewedText(text: string): boolean {
    if (!this.canSend || !text.trim() || text.length > 2000) return false;
    this.send({type: 'conversation.item.create', item: {type: 'message', role: 'user', content: [{type: 'input_text', text: 'Texte de ma demande relu et confirmé : ' + text.trim()}]}});
    this.send({type: 'response.create'}); this.responding = true; this.notify();
    return true;
  }
  fail(message: string) { this.close(); this.options.fault(message); }
  close() {
    if (this.closed) return;
    this.closed = true; this.abort.abort();
    if (this.timeout) clearTimeout(this.timeout);
    if (this.deadline) clearTimeout(this.deadline);
    this.timeout = this.deadline = null;
    if (this.dc) { this.dc.onclose = null; this.dc.close(); }
    this.pc?.close(); this.pc = null; this.dc = null;
    if (this.speaker) { this.speaker.pause(); this.speaker.srcObject = null; this.speaker = null; }
    this.toolOutputs = []; this.seenCalls.clear(); this.options.state('closed');
  }
}
