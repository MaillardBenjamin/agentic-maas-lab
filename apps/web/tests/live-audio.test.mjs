import test from 'node:test';
import assert from 'node:assert/strict';
import { LiveAudio } from '../src/live-audio.ts';

function harness(overrides = {}) {
  const sent = [], added = [], faults = [], captions = [], states = [];
  const dc = {readyState: 'open', send: value => sent.push(JSON.parse(value)), close() {this.readyState = 'closed';}};
  const pc = {closed: false, addTrack: track => added.push(track), createDataChannel: () => dc, createOffer: async () => ({type: 'offer', sdp: 'audio-only-offer'}), setLocalDescription: async () => {}, setRemoteDescription: async () => dc.onopen?.(), close() {this.closed = true;}};
  const speaker = {autoplay: false, pause() {this.paused = true;}, play: async () => {}};
  const stream = {getAudioTracks: () => [{kind: 'audio', id: 'microphone'}], getVideoTracks: () => {throw new Error('Audio transport must not inspect camera');}};
  const options = {api: async () => ({value: 'ek_ephemeral', audio_only: true, video_sent_to_openai: false, client_duration_limit_seconds: 180}), stream, ask: async question => 'Consultation: ' + question, state: value => states.push(value), caption: value => captions.push(value), fault: value => faults.push(value), expired: () => {}, soundBlocked: () => {}, ...overrides};
  const runtime = {peer: () => pc, audio: () => speaker, fetch: async () => ({ok: true, text: async () => 'answer'})};
  return {live: new LiveAudio(options, runtime), dc, pc, sent, added, faults, captions, states, speaker};
}

test('the realtime peer receives microphone tracks only, and reviewed input contains text only', async () => {
  const h = harness();
  try {
    await h.live.open();
    assert.deepEqual(h.added.map(track => track.kind), ['audio']);
    assert.equal(h.live.shareReviewedText('Je souhaite connaître le tarif.'), true);
    const message = h.sent.find(event => event.type === 'conversation.item.create');
    assert.deepEqual(message.item.content.map(part => part.type), ['input_text']);
    assert.ok(!JSON.stringify(h.sent).includes('image'));
    assert.equal(h.live.shareReviewedText('Deuxième envoi trop rapide'), false);
  } finally {h.live.close();}
  assert.equal(h.pc.closed, true);
  assert.equal(h.speaker.paused, true);
});

test('stopping during credential creation prevents a late peer or audio connection', async () => {
  let resolve;
  const pending = new Promise(value => {resolve = value;});
  const h = harness({api: () => pending});
  const start = h.live.open(); h.live.close();
  resolve({value: 'ek_late', audio_only: true, video_sent_to_openai: false});
  await start;
  assert.equal(h.live.pc, null);
  assert.deepEqual(h.added, []);
});

test('tool results wait until the current response ends, and duplicate calls execute once', async () => {
  let count = 0;
  const h = harness({ask: async () => {count++; return 'Tarif obtenu par le service métier.';}});
  try {
    await h.live.open(); h.live.receive({type: 'response.created'});
    const call = {type: 'response.function_call_arguments.done', name: 'ask_ticketing_agent', call_id: 'same-call', arguments: JSON.stringify({question: 'Quel tarif ?'})};
    await h.live.call(call); await h.live.call(call);
    assert.equal(count, 1);
    assert.equal(h.sent.length, 0);
    h.live.receive({type: 'response.done'});
    assert.deepEqual(h.sent.map(value => value.type), ['conversation.item.create', 'response.create']);
    assert.equal(h.sent[0].item.type, 'function_call_output');
  } finally {h.live.close();}
});

test('an unknown tool, injected arguments or a closed session cannot run a business consultation', async () => {
  let count = 0;
  const h = harness({ask: async () => {count++; return 'result';}});
  try {
    await h.live.open();
    await h.live.call({name: 'pay', call_id: 'pay', arguments: '{}'});
    await h.live.call({name: 'ask_ticketing_agent', call_id: 'injected', arguments: '{"question":"question","order_id":"foreign"}'});
    assert.equal(count, 0);
    h.live.close();
    h.live.receive({type: 'response.output_audio_transcript.delta', delta: 'Late caption'});
    assert.deepEqual(h.captions, []);
  } finally {h.live.close();}
});

test('a rejected connection releases the peer and never retries another provider', async () => {
  const h = harness();
  h.live.runtime.fetch = async () => ({ok: false});
  await h.live.open();
  assert.equal(h.live.closed, true);
  assert.equal(h.pc.closed, true);
  assert.equal(h.faults.length, 1);
  assert.deepEqual(h.sent, []);
});
