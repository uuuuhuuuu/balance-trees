import test from 'node:test';
import assert from 'node:assert/strict';
import { FLAVORS, ORDERS, simulate, makeSequence } from '../src/balance_trees/showcase/site/dist/model.mjs';
import { LargeTree, createSequence, VISIBLE_LIMIT } from '../src/balance_trees/showcase/site/dist/large-model.mjs';
import { initialTheme, readPreference, savePreference, THEME_KEY } from '../src/balance_trees/showcase/site/dist/interface.mjs';

function finish(tree) { while (tree.advance()) {} return tree.snapshot(); }
function topology(nodes) { return [...nodes].sort((a, b) => a.key - b.key).map(n => [n.key, n.left, n.right, n.priority]); }
function independentMetrics(tree) {
  const stack = tree.root < 0 ? [] : [[tree.root, 0]];
  let total = 0, height = 0, count = 0;
  while (stack.length) {
    const [id, depth] = stack.pop(); total += depth; height = Math.max(height, depth); count++;
    for (const child of [tree.left[id], tree.right[id]]) if (child >= 0) stack.push([child, depth + 1]);
  }
  return { height, mean: count ? total / count : 0, count };
}

test('large engine matches detailed engine for every strategy and sequence family', () => {
  for (const strategy of Object.keys(FLAVORS)) for (const order of Object.keys(ORDERS).filter(x => x !== 'custom')) for (const seed of [0, 2026]) {
    const config = { strategy, order, count: 30, seed };
    const actual = finish(new LargeTree(config));
    const expected = simulate(makeSequence(order, 30, seed), strategy, seed).frames.at(-1);
    assert.deepEqual(topology(actual.nodes), topology(expected.nodes), `${strategy} / ${order} / ${seed}`);
    for (const field of ['nodes', 'height', 'mean_depth', 'rotations', 'visits', 'random_bits', 'scanned_nodes']) assert.equal(actual.stats[field], expected.stats[field], `${strategy} / ${order}: ${field}`);
  }
});
test('incremental mean depth and height match independent traversal after each rotation', () => {
  for (const strategy of Object.keys(FLAVORS)) {
    const tree = new LargeTree({ strategy, sequence: [8, 4, 12, 2, 6, 10, 14, 3, 0, -2, 4, 11], seed: 17 });
    while (tree.advance()) if (['rotate', 'insert', 'settled'].includes(tree.current.kind)) {
      const measured = independentMetrics(tree), frame = tree.snapshot();
      assert.equal(frame.stats.height, measured.height);
      assert.equal(frame.stats.mean_depth, measured.mean);
      assert.equal(frame.stats.nodes, measured.count);
    }
  }
});
test('large engine preserves duplicates, signed keys and CSV validation', () => {
  const tree = new LargeTree({ strategy: 'treap', text: '8, -4, 0, +12, 8', seed: 42 });
  const result = finish(tree);
  assert.equal(result.stats.nodes, 4); assert.equal(result.stats.random_bits, 128);
  for (const text of ['', '1,,2', '1.5,2', '9007199254740992']) assert.throws(() => createSequence({ text }));
});
test('large snapshots stay connected and bounded while full statistics cover the whole tree', () => {
  const tree = new LargeTree({ strategy: 'none', order: 'increasing', count: 10000, seed: 42 });
  const frame = finish(tree), nodes = new Map(frame.nodes.map(node => [node.key, node]));
  assert.equal(frame.stats.nodes, 10000); assert.equal(frame.stats.height, 9999);
  assert.equal(frame.stats.mean_depth, 4999.5); assert.equal(frame.windowed, true);
  assert.ok(frame.nodes.length <= VISIBLE_LIMIT);
  const seen = new Set(), stack = [frame.root];
  while (stack.length) {
    const key = stack.pop(), node = nodes.get(key); assert.ok(node); assert.ok(!seen.has(key)); seen.add(key);
    if (node.left !== null) stack.push(node.left);
    if (node.right !== null) stack.push(node.right);
  }
  assert.equal(seen.size, frame.nodes.length);
});
test('million-key runs allocate typed storage and retain no full-tree history', () => {
  const tree = new LargeTree({ strategy: 'none', order: 'increasing', count: 1000000, seed: 2026 });
  const result = finish(tree);
  assert.equal(result.stats.nodes, 1000000);
  assert.equal(result.stats.mean_depth, 499999.5);
  assert.equal(result.stats.height, 999999);
  assert.ok(result.nodes.length <= VISIBLE_LIMIT);
  assert.ok(tree.left instanceof Int32Array);
  assert.equal(tree.frames, undefined);
});
test('themes use saved choice, system default, and survive unavailable storage', () => {
  const values = new Map(), storage = { getItem: k => values.get(k), setItem: (k, v) => values.set(k, v) };
  assert.equal(initialTheme(storage, true), 'dark');
  savePreference(storage, THEME_KEY, 'light'); assert.equal(initialTheme(storage, true), 'light');
  const blocked = { getItem() { throw new Error('Blocked'); }, setItem() { throw new Error('Blocked'); } };
  assert.equal(readPreference(blocked, THEME_KEY), null);
  assert.equal(initialTheme(blocked, false), 'light');
  assert.doesNotThrow(() => savePreference(blocked, THEME_KEY, 'dark'));
});

test('production worker streams a complete fast-forward run through StreamPlayer', { timeout: 15000 }, async () => {
  const { Worker: NodeWorker } = await import('node:worker_threads');
  const { StreamPlayer } = await import('../src/balance_trees/showcase/site/dist/stream-player.mjs');
  const previous = globalThis.Worker;
  globalThis.Worker = class {
    constructor() {
      this.worker = new NodeWorker(new URL('./showcase-worker-harness.mjs', import.meta.url));
      this.worker.on('message', data => this.onmessage?.({ data }));
      this.worker.on('error', failure => this.onerror?.(failure));
    }
    postMessage(message) { this.worker.postMessage(message); }
    terminate() { this.worker.terminate(); }
  };
  let runner;
  try {
    await new Promise((resolve, reject) => {
      runner = new StreamPlayer({ strategy: 'treap', order: 'random', count: 5000, seed: 2026 },
        frame => { if (runner.done) { assert.equal(frame.stats.nodes, 5000); resolve(); } },
        message => reject(new Error(message)),
        ready => ready.play());
      runner.setDelay(0);
    });
    assert.equal(runner.playing, false);
    assert.ok(runner.trace.frames.length <= 128);
    assert.ok(runner.frame.nodes.length <= VISIBLE_LIMIT);
    assert.equal(runner.trace.sequence.length, 32);
  } finally { runner?.dispose(); globalThis.Worker = previous; }
});

test('one-million-key random treap keeps exact global metrics and a valid priority heap', { timeout: 90000 }, () => {
  const tree = new LargeTree({ strategy: 'treap', order: 'random', count: 1000000, seed: 2026 });
  const result = finish(tree), independent = independentMetrics(tree);
  assert.equal(result.stats.nodes, 1000000);
  assert.equal(independent.count, 1000000);
  assert.equal(result.stats.mean_depth, independent.mean);
  assert.equal(result.stats.height, independent.height);
  assert.ok(result.nodes.length <= VISIBLE_LIMIT);
  for (let id = 0; id < tree.length; id++) if (tree.parent[id] >= 0) assert.equal(tree.higher(id, tree.parent[id]), false);
});

test('worker lottery adapters count real scans and enforce the local budget', () => {
  for (const strategy of ['recount-root', 'window-root']) {
    const count = strategy === 'recount-root' ? 128 : 2048;
    const tree = new LargeTree({ strategy, count, order: 'converging', seed: 2026 });
    let previous = 0;
    while (tree.advance()) if (tree.current.kind === 'settled') {
      const scans = tree.scans - previous;
      if (strategy === 'window-root') { assert.ok(scans <= 64); assert.ok(tree.insertionRotations <= 63); }
      else assert.equal(scans, tree.insertion);
      previous = tree.scans;
    }
    assert.equal(tree.snapshot().stats.nodes, count);
    if (strategy === 'recount-root') assert.equal(tree.scans, count * (count + 1) / 2);
  }
});

test('compact chain snapshots bound depth and label hidden descendants', () => {
  const tree = new LargeTree({ strategy: 'none', order: 'increasing', count: 10000, seed: 42 });
  finish(tree);
  tree.focusId = 0;
  const frame = tree.snapshot(), nodes = new Map(frame.nodes.map(node => [node.key, node]));
  const stack = [[frame.root, 0]];
  let depth = 0;
  while (stack.length) {
    const [key, d] = stack.pop(), node = nodes.get(key); depth = Math.max(depth, d);
    for (const child of [node.left, node.right]) if (child !== null) stack.push([child, d + 1]);
  }
  assert.ok(depth <= 8);
  assert.equal(frame.stats.nodes, 10000);
  const frontier = frame.nodes.find(node => node.hidden_right > 0);
  assert.ok(frontier); assert.equal(frontier.hidden_right, 10000 - frontier.key);
});

test('compact layout keeps a one-child path in one column', async () => {
  const { treeLayout } = await import('../src/balance_trees/showcase/site/dist/layout.mjs');
  const frame = simulate([1, 2, 3, 4, 5], 'none', 42).frames.at(-1);
  const points = treeLayout(frame, [1, 2, 3, 4, 5], true);
  assert.equal(new Set([...points.values()].map(p => p.x)).size, 1);
  assert.equal(points.get(5).y, 4 * 68);
});

test('browser factory covers the catalog and rejects missing implementations', async () => {
  const { createStrategy, strategyNames, targetDepth } = await import('../src/balance_trees/showcase/site/dist/strategies.mjs');
  assert.deepEqual(strategyNames().sort(), Object.keys(FLAVORS).sort());
  assert.throws(() => createStrategy('missing', {}), /No browser implementation/);
  assert.equal(targetDepth(50n, 100n, 200n, 2, 8), 0);
  assert.equal(targetDepth(300n, 100n, 200n, 2, 8), 8);
  assert.deepEqual([0n, 9n, 10n, 29n, 30n, 70n].map(p => targetDepth(p, 0n, 70n, 4, 9)), [0, 0, 1, 1, 2, 2]);
});

test('random-level stays at shallow leaves and rotates only the sampled depth difference', async () => {
  const { createStrategy } = await import('../src/balance_trees/showcase/site/dist/strategies.mjs');
  for (const [depth, priority, target] of [[1, 30n, 1], [2, 30n, 2], [5, 30n, 2], [5, 10n, 1], [5, 0n, 0]]) {
    let bits = [], rotations = 0;
    const events = [], node = {};
    const strategy = createStrategy('random-level', {
      bit: () => { assert.ok(bits.length); return bits.shift(); },
      event: function* (kind, title, detail) { events.push({ kind, title, detail }); },
      promote: function* (cursor) { assert.equal(cursor, node); rotations++; },
    });
    function insert(roll, insertionDepth) {
      bits = [...roll.toString(2).padStart(64, '0')].map(Number);
      [...strategy(node, insertionDepth)];
      assert.equal(bits.length, 0);
    }
    // Seven prior rolls give three depth bands with boundaries 10 and 30.
    for (const roll of [0n, 70n, 70n, 70n, 70n, 70n, 70n]) insert(roll, 0);
    rotations = 0;
    insert(priority, depth);
    assert.equal(rotations, depth - target);
    assert.equal(events.at(-1).title, `Target depth ${target}`);
  }
});

test('narrow-screen windows keep focus connected within twelve nodes and four levels', () => {
  const tree = new LargeTree({ strategy: 'hash-priority', order: 'random', count: 1000, seed: 42, visibleLimit: 12, visibleDepth: 4 });
  const frame = finish(tree), nodes = new Map(frame.nodes.map(node => [node.key, node]));
  assert.ok(nodes.size <= 12); assert.ok(nodes.has(frame.focus));
  const pending = [[frame.root, 0]], seen = new Set();
  while (pending.length) {
    const [key, depth] = pending.pop(); assert.ok(depth <= 4); seen.add(key);
    for (const child of [nodes.get(key).left, nodes.get(key).right]) if (child !== null) pending.push([child, depth + 1]);
  }
  assert.equal(seen.size, nodes.size);
  assert.equal(frame.stats.nodes, 1000);
});

test('random-level v2 preserves duplicates and counts ancestor walks in both engines', () => {
  const sequence = [0, 20, 1, 19, 2, 18, 3, 17, 4, 16, 5, 15, 6, 14, 7, 13, 8, 12, 9, 11, 10, 10, -1];
  const expected = simulate(sequence, 'random-level-v2', 2026).frames.at(-1);
  const actual = finish(new LargeTree({ strategy: 'random-level-v2', sequence, seed: 2026 }));
  assert.equal(actual.stats.nodes, 22);
  assert.equal(actual.stats.random_bits, 22 * 64);
  assert.ok(actual.stats.visits > 0);
  assert.deepEqual(topology(actual.nodes), topology(expected.nodes));
  for (const field of ['nodes', 'rotations', 'visits', 'random_bits', 'mean_depth', 'height']) {
    assert.equal(actual.stats[field], expected.stats[field]);
  }
});
