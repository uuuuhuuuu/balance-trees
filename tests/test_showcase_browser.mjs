import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { FLAVORS, ORDERS, makeSequence, parseSequence, simulate, validateTrace } from '../src/balance_trees/showcase/site/dist/model.mjs';
import { TracePlayer } from '../src/balance_trees/showcase/site/dist/player.mjs';

test('CSV input is strict and supports signed keys and duplicates', () => {
  assert.deepEqual(parseSequence(' 8, -4,\n0, +12, 8 '), [8, -4, 0, 12, 8]);
  for (const value of ['', '1,,2', '1,', '1 2', '1.5,2', 'NaN', '9007199254740992']) assert.throws(() => parseSequence(value));
  assert.equal(parseSequence(Array(1000).fill('1').join(',')).length, 1000);
});
test('all presets produce reproducible permutations for even and odd sizes', () => {
  for (const order of Object.keys(ORDERS).filter(name => name !== 'custom')) for (const count of [1, 7, 16]) {
    const values = makeSequence(order, count, 42);
    assert.deepEqual([...values].sort((a, b) => a - b), Array.from({ length: count }, (_, i) => i + 1));
    assert.deepEqual(values, makeSequence(order, count, 42));
  }
  assert.deepEqual(makeSequence('converging', 6, 42), [1, 6, 2, 5, 3, 4]);
});
test('every frame of every browser flavor preserves the BST invariant', () => {
  for (const flavor of Object.keys(FLAVORS)) for (const order of Object.keys(ORDERS).filter(name => name !== 'custom')) for (const seed of [0, 9]) {
    const trace = simulate(makeSequence(order, 16, seed), flavor, seed);
    assert.equal(validateTrace(trace), trace);
    const final = trace.frames.at(-1);
    assert.equal(final.stats.nodes, 16);
    assert.equal(trace.frames.filter(frame => frame.kind === 'rotate').length, final.stats.rotations);
    if (flavor === 'treap') for (const frame of trace.frames.filter(frame => frame.kind === 'settled')) assert.equal(frame.heap_valid, true);
  }
});
test('duplicate insertion consumes no extra randomness in all flavors', () => {
  for (const flavor of Object.keys(FLAVORS)) {
    const settled = simulate([4, 2, 4], flavor).frames.filter(frame => frame.kind === 'settled');
    assert.equal(settled[2].stats.random_bits, settled[1].stats.random_bits);
    assert.equal(settled[2].stats.nodes, 2);
    assert.equal(settled[2].stats.insertion_rotations, 0);
  }
});
test('inverse-depth degenerates on monotone input, matching the Python rule', () => {
  const final = simulate(makeSequence('increasing', 32, 42), 'inverse-depth').frames.at(-1);
  assert.equal(final.stats.height, 31);
  assert.equal(final.stats.mean_depth, 15.5);
  assert.equal(final.stats.random_bits, 0);
});
test('each primitive rotation exposes its before and after state', () => {
  const trace = simulate(makeSequence('increasing', 16, 42), 'treap');
  for (let i = 0; i < trace.frames.length; i++) if (trace.frames[i].kind === 'prepare') {
    const before = trace.frames[i], after = trace.frames[i + 1];
    assert.equal(after.kind, 'rotate');
    assert.equal(after.stats.rotations, before.stats.rotations + 1);
    assert.equal(after.promoted, before.promoted);
  }
});
test('browser simulation is replayable from its seed', () => {
  const values = makeSequence('random', 20, 42);
  assert.deepEqual(simulate(values, 'treap', 9), simulate(values, 'treap', 9));
});
test('the viewer accepts actual Python traces for every implementation', () => {
  const result = spawnSync('python', ['-c', 'import json; from balance_trees.showcase import build_trace; from balance_trees.strategies import STRATEGIES; print(json.dumps([build_trace([8,4,12,2,6,10,14], s, 2026) for s in ["treap",*STRATEGIES]]))'], { encoding: 'utf8', env: { ...process.env, PYTHONPATH: 'src' }, maxBuffer: 10 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr);
  for (const trace of JSON.parse(result.stdout)) assert.equal(validateTrace(trace), trace);
});
test('the trace importer rejects cycles, disconnected nodes and bad metrics', () => {
  const trace = simulate([2, 1, 3]);
  const cycle = structuredClone(trace); cycle.frames.at(-1).nodes[0].left = cycle.frames.at(-1).nodes[0].key;
  assert.throws(() => validateTrace(cycle));
  const disconnected = structuredClone(trace); disconnected.frames.at(-1).root = null;
  assert.throws(() => validateTrace(disconnected));
  const badMetrics = structuredClone(trace); badMetrics.frames[0].stats.height = -1;
  assert.throws(() => validateTrace(badMetrics));
});
test('player steps backward, jumps to rotations and insertions, and clamps its timeline', () => {
  const player = new TracePlayer(); player.load(simulate([1, 2, 3, 4]));
  player.step(); assert.equal(player.index, 1);
  player.step(-1); assert.equal(player.index, 0);
  player.nextInsertion(); assert.equal(player.frame.kind, 'settled'); assert.equal(player.frame.insertion, 1);
  player.nextRotation(); assert.equal(player.frame.kind, 'rotate');
  player.seek(99999); assert.equal(player.index, player.trace.frames.length - 1);
  player.seek(-1); assert.equal(player.index, 0);
});
test('autoplay stops on the final frame and can restart', async () => {
  let completed;
  const done = new Promise(resolve => { completed = resolve; });
  const player = new TracePlayer((frame, index, playing) => { if (frame?.kind === 'settled' && !playing) completed(); });
  player.load(simulate([1])); player.setDelay(1); player.play();
  await done;
  assert.equal(player.playing, false); assert.equal(player.index, player.trace.frames.length - 1);
  player.play(); assert.equal(player.index, 0); player.pause();
});

test('static browser mode makes no Python API requests', async () => {
  const { detectEngine } = await import('../src/balance_trees/showcase/site/dist/runtime.mjs');
  let requests = 0;
  const engine = await detectEngine('https://example.github.io/trees/', 'browser', async () => { requests++; throw new Error('Unexpected request'); });
  assert.equal(engine, 'browser'); assert.equal(requests, 0);
});
test('Python discovery respects the repository subpath and bounds the request', async () => {
  const { detectEngine } = await import('../src/balance_trees/showcase/site/dist/runtime.mjs');
  let requested;
  const engine = await detectEngine('https://example.github.io/trees/', 'auto', async (url, options) => {
    requested = url.pathname; assert.ok(options.signal instanceof AbortSignal);
    return { ok: true, json: async () => ({ engine: 'python' }) };
  });
  assert.equal(requested, '/trees/api/config'); assert.equal(engine, 'python');
});
test('static hosts and unavailable APIs fall back to browser simulation', async () => {
  const { detectEngine } = await import('../src/balance_trees/showcase/site/dist/runtime.mjs');
  for (const request of [
    async () => ({ ok: false }),
    async () => ({ ok: true, json: async () => { throw new Error('HTML response'); } }),
    async () => { throw new Error('Network unavailable'); },
  ]) assert.equal(await detectEngine('https://example.github.io/trees/', 'auto', request), 'browser');
});

test('detailed fast-forward batches display events and still reaches the final state', { timeout: 6000 }, async () => {
  let completed;
  const done = new Promise(resolve => { completed = resolve; });
  const shown = [];
  const player = new TracePlayer((frame, index, playing) => {
    if (!frame) return;
    shown.push(index);
    if (!playing && frame.kind === 'settled' && index === player.trace.frames.length - 1) completed();
  });
  player.load(simulate(makeSequence('random', 32, 42), 'treap', 42));
  player.setDelay(0); player.play(); await done;
  assert.equal(player.frame.stats.nodes, 32);
  assert.equal(player.playing, false);
  assert.ok(shown.length < player.trace.frames.length);
});
