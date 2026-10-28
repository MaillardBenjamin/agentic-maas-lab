import test from 'node:test';
import assert from 'node:assert/strict';
import { acquireWebcam, recordWebcamPhrase } from '../src/webcam-capture.ts';

function fake() {
  const tracks = [{kind: 'video'}, {kind: 'audio'}], selected = [];
  const recorder = {state: 'inactive', mimeType: 'video/webm', start() {this.state = 'recording';}, stop() {this.state = 'inactive'; this.onstop?.();}};
  const source = {getTracks: () => tracks, getVideoTracks: () => tracks.filter(track => track.kind === 'video')};
  const runtime = {stream: tracks => {selected.push(...tracks); return {tracks};}, recorder: () => recorder, supported: () => true};
  return {recorder, source, runtime, selected};
}
test('a lip-only phrase takes video from the active webcam and excludes the microphone', async () => {
  const h = fake(), capture = recordWebcamPhrase(h.source, true, h.runtime);
  h.recorder.ondataavailable({data: new Blob(['captured-webcam-bytes'])});
  h.recorder.stop();
  const blob = await capture.result;
  assert.deepEqual(h.selected.map(track => track.kind), ['video']);
  assert.equal(await blob.text(), 'captured-webcam-bytes');
});
test('canceling a phrase drops captured data while leaving track ownership with the webcam', async () => {
  const h = fake(), capture = recordWebcamPhrase(h.source, false, h.runtime);
  h.recorder.ondataavailable({data: new Blob(['private'])});
  capture.cancel();
  await assert.rejects(capture.result, {name: 'AbortError'});
  assert.equal(h.recorder.state, 'inactive');
  assert.deepEqual(h.selected.map(track => track.kind), ['video', 'audio']);
});
test('a recorder error cannot turn a partial phrase into a successful transcription request', async () => {
  const h = fake(), capture = recordWebcamPhrase(h.source, true, h.runtime);
  h.recorder.ondataavailable({data: new Blob(['partial'])}); h.recorder.onerror();
  await assert.rejects(capture.result, /capture webcam/);
});
test('a camera permission granted after cancellation releases every track immediately', async () => {
  const stopped = [];
  const stream = {getTracks: () => [0, 1].map(id => ({stop: () => stopped.push(id)}))};
  const result = await acquireWebcam(true, () => false, async () => stream);
  assert.equal(result, null);
  assert.deepEqual(stopped, [0, 1]);
});
