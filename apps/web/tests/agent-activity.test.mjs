import test from 'node:test';
import assert from 'node:assert/strict';
import { actorState, mergeExchanges } from '../src/agent-activity-state.ts';
const entry = (id, sequence, state = 'started', source = 'conversation', target = 'tariffs') => ({run_id: 'run', span_id: id, sequence, state, source, target, at: '', protocol: 'A2A', duration_ms: null});

test('a completion updates the observed exchange without duplicating it or regressing on delayed data', () => {
  const completed = mergeExchanges([entry('one', 1)], [entry('one', 3, 'completed')]);
  assert.equal(completed.length, 1);
  assert.equal(completed[0].state, 'completed');
  assert.equal(mergeExchanges(completed, [entry('one', 1)])[0].state, 'completed');
});
test('one completed tool does not mark an agent idle while another exchange is running', () => {
  const values = [entry('one', 1), entry('two', 2, 'completed', 'tariffs', 'read_catalog')];
  assert.equal(actorState(values, 'tariffs'), 'started');
  assert.equal(actorState(values, 'parking'), 'idle');
  assert.equal(actorState([entry('one', 3, 'failed')], 'tariffs'), 'failed');
});
test('the browser keeps a bounded history and never invents an exchange', () => {
  assert.deepEqual(mergeExchanges([], []), []);
  const values = mergeExchanges([], Array.from({length: 600}, (_, n) => entry(String(n), n)));
  assert.equal(values.length, 512);
  assert.equal(values.at(-1).sequence, 599);
});
