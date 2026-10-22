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
  const badScans = structuredClone(trace); badScans.frames[0].stats.scanned_nodes = -1;
  assert.throws(() => validateTrace(badScans));
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

test('scrollable event history renders bounded rows and seeks by click and keyboard', async () => {
  const { EventTimeline } = await import('../src/balance_trees/showcase/site/dist/timeline.mjs');
  // Small DOM substitute exercises the production widget without a browser process.
  const document = { activeElement: null, createElement() { return new Element(); } };
  class Element {
    constructor() { this.children = []; this.dataset = {}; this.style = {}; this.attributes = {}; this.listeners = {}; this.ownerDocument = document; this.scrollTop = 0; this.clientHeight = 176; }
    addEventListener(type, handler) { this.listeners[type] = handler; }
    setAttribute(key, value) { this.attributes[key] = value; }
    append(child) { child.parent = this; this.children.push(child); }
    replaceChildren(...children) { this.children = []; children.forEach(child => this.append(child)); }
    contains(node) { return this.children.includes(node); }
    closest() { return this.dataset.index !== undefined ? this : this.parent?.closest(); }
    querySelector(selector) { const index = selector.match(/data-index="(\d+)"/)[1]; return this.children.find(child => String(child.dataset.index) === index); }
    focus() { document.activeElement = this; }
  }
  const container = new Element(); container.firstElementChild = new Element();
  const frames = Array.from({ length: 20000 }, (_, i) => ({ title: `Event ${i}`, insertion: Math.floor(i / 4), kind: 'rotate', description: 'A rotation.' }));
  let selected;
  const timeline = new EventTimeline(container, index => { selected = index; timeline.update(frames, index); });
  timeline.update(frames, 0);
  assert.ok(container.firstElementChild.children.length < 20);
  container.scrollTop = 44000; container.listeners.scroll();
  const row = container.firstElementChild.children[3];
  container.listeners.click({ target: row });
  assert.equal(selected, Number(row.dataset.index));
  assert.equal(container.firstElementChild.querySelector(`[data-index="${selected}"]`).attributes['aria-current'], 'step');
  let prevented = false;
  container.listeners.keydown({ key: 'End', preventDefault() { prevented = true; } });
  assert.equal(selected, 19999); assert.equal(prevented, true);
  assert.equal(Number(document.activeElement.dataset.index), 19999);
  assert.ok(container.firstElementChild.children.length < 20);
  container.listeners.keydown({ key: 'Home', preventDefault() {} });
  assert.equal(selected, 0); assert.equal(container.scrollTop, 0);
});

test('worker snapshots arriving after pause preserve the inspected historical event', async () => {
  const { StreamPlayer } = await import('../src/balance_trees/showcase/site/dist/stream-player.mjs');
  const previous = globalThis.Worker;
  globalThis.Worker = class { postMessage() {} terminate() {} };
  let runner;
  try {
    runner = new StreamPlayer({ strategy: 'treap', count: 5000, seed: 1 }, () => {}, message => assert.fail(message), () => {});
    const send = (number, extra = {}) => runner.worker.onmessage({ data: { frame: { title: String(number) }, running: true, done: false, ...extra } });
    send(0, { ready: true, preview: [], count: 5000 }); send(1); send(2);
    runner.pause(); runner.seek(0);
    send(3); // A frame already queued by the worker before it received pause.
    assert.equal(runner.frame.title, '0'); assert.equal(runner.playing, false);
    assert.equal(runner.trace.frames.at(-1).title, '3');
    runner.play(); send(4);
    assert.equal(runner.frame.title, '4'); assert.equal(runner.playing, true);
  } finally { runner?.dispose(); globalThis.Worker = previous; }
});

test('recomputed priorities match Python exactly without storing node priorities', async () => {
  const { hashPriority } = await import('../src/balance_trees/showcase/site/dist/priority-free.mjs');
  const keys = [-9007199254740991, -100, -1, 0, 1, 42, 9007199254740991];
  const seeds = [0, 42, 2026];
  const code = 'import json; from balance_trees.strategies.hashed import key_priority; from balance_trees.showcase import build_trace; keys=[-9007199254740991,-100,-1,0,1,42,9007199254740991]; print(json.dumps([{ "seed":s, "priorities":[str(key_priority(k,s)) for k in keys], "trace":build_trace(keys+[0],"hash-priority",s) } for s in [0,42,2026]]))';
  const result = spawnSync('python', ['-c', code], { encoding: 'utf8', env: { ...process.env, PYTHONPATH: 'src' }, maxBuffer: 5 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr);
  for (const expected of JSON.parse(result.stdout)) {
    assert.deepEqual(keys.map(key => hashPriority(key, expected.seed).toString()), expected.priorities);
    const actual = simulate([...keys, 0], 'hash-priority', expected.seed).frames.at(-1);
    assert.deepEqual(actual.nodes, expected.trace.frames.at(-1).nodes);
    assert.deepEqual(actual.stats, expected.trace.frames.at(-1).stats);
    assert.ok(actual.nodes.every(node => node.priority === null));
  }
});
