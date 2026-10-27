// One policy implementation for both object-node traces and typed-array workers.
// Adapters supply tree primitives and yield events; policies never read view caches.
import { hashPriority, rootLottery } from './priority-free.mjs';

const factories = new Map();
export function registerStrategy(name, factory) {
  if (factories.has(name)) throw new Error(`Strategy already registered: ${name}`);
  factories.set(name, factory);
}
export function createStrategy(name, context) {
  const factory = factories.get(name);
  if (!factory) throw new Error(`No browser implementation for strategy: ${name}`);
  return factory(context);
}
export const strategyNames = () => [...factories.keys()];

registerStrategy('none', () => function* () {});
registerStrategy('treap', c => function* (node) {
  while (c.parent(node) !== null) {
    c.visit();
    const violation = c.higher(node, c.parent(node));
    yield* c.event('priority', `Compare priorities at ${c.key(node)}`, violation ? 'Promote the child.' : 'Heap order holds; stop.', node);
    if (!violation) break;
    yield* c.promote(node);
  }
});
registerStrategy('hash-priority', c => function* (node) {
  const priority = hashPriority(c.key(node), c.seed);
  while (c.parent(node) !== null) {
    c.visit();
    const other = hashPriority(c.key(c.parent(node)), c.seed);
    const violation = priority < other || (priority === other && c.key(node) < c.key(c.parent(node)));
    yield* c.event('priority', `Recompute priorities at ${c.key(node)}`, `Key hash ${priority.toString(16)}; parent hash ${other.toString(16)}. ${violation ? 'Promote the child.' : 'Heap order holds; stop.'} Values are discarded.`, node);
    if (!violation) break;
    yield* c.promote(node);
  }
});
for (const [name, budget] of [['recount-root', Infinity], ['window-root', 64]]) {
  registerStrategy(name, c => function* (node) { yield* rootLottery(node, c, budget); });
}
for (const name of ['halving', 'constant-half', 'inverse-depth']) {
  registerStrategy(name, c => function* (node, depth) {
    let denominator = name === 'inverse-depth' ? BigInt(depth) : 2n;
    while (node !== null && c.parent(node) !== null) {
      if (yield* c.choose(node, 1n, denominator)) yield* c.promote(node);
      node = c.parent(node);
      if (name === 'halving') denominator *= 2n;
    }
  });
}
for (const name of ['paper-zig', 'paper-zigzag']) {
  registerStrategy(name, c => function* (node) {
    while (c.parent(node) !== null) {
      if (yield* c.choose(node, name === 'paper-zig' ? 1 : 3, name === 'paper-zig' ? 2 : 4, 'continue')) { node = c.parent(node); continue; }
      if (name === 'paper-zig') yield* c.promote(node);
      else {
        const parent = c.parent(node), grandparent = c.parent(parent);
        if (grandparent !== null) {
          if ((c.left(parent) === node) === (c.left(grandparent) === parent)) yield* c.promote(parent);
          else { yield* c.promote(node); yield* c.promote(node); }
        }
      }
      break;
    }
  });
}

// Integer bands mirror Python exactly, without float rounding of 64-bit rolls.
export function targetDepth(priority, lowest, highest, count, insertionDepth) {
  if (lowest === null || priority < lowest) return 0;
  if (priority > highest) return insertionDepth;
  if (highest === lowest) return 0;
  const levels = Math.max(1, Math.floor(Math.log2(Math.max(1, count))) + 1);
  const weight = (1n << BigInt(levels)) - 1n, span = highest - lowest;
  let cumulative = 0n;
  for (let depth = 0; depth < levels; depth++) {
    cumulative += span * (1n << BigInt(depth)) / weight;
    if (priority - lowest < cumulative || depth === levels - 1) return depth;
  }
}
registerStrategy('random-level', c => {
  let count = 0, lowest = null, highest = null;
  return function* (node, depth) {
    let priority = 0n;
    for (let bit = 0; bit < 64; bit++) priority = (priority << 1n) | BigInt(c.bit());
    const sampled = targetDepth(priority, lowest, highest, count, depth);
    const target = Math.min(depth, sampled);
    count++;
    if (lowest === null || priority < lowest) lowest = priority;
    if (highest === null || priority > highest) highest = priority;
    yield* c.event('target', `Target depth ${target}`, `Rolled ${priority}; sampled depth ${sampled} from the previous interval. Stay at insertion depth ${depth} if the sampled level is equally deep or deeper; otherwise rotate upward ${depth - target} times. No per-node priority is retained.`, node);
    if (target === depth) return;
    for (let current = depth; current > target; current--) yield* c.promote(node);
  };
});
registerStrategy('random-level-v2', c => {
  let count = 0, lowest = null, highest = null;
  return function* (node, depth) {
    let priority = 0n;
    for (let bit = 0; bit < 64; bit++) priority = (priority << 1n) | BigInt(c.bit());
    const target = targetDepth(priority, lowest, highest, count, depth);
    const isRecord = lowest !== null && priority < lowest;
    count++;
    if (lowest === null || priority < lowest) lowest = priority;
    if (highest === null || priority > highest) highest = priority;
    yield* c.event('target', `Repair level ${target}`, `Rolled ${priority}; choose a level from the previous interval. ${isRecord ? 'A strict new minimum promotes the leaf to the root.' : 'Repair the path at that level with at most two rotations.'} No per-node priority is retained.`, node);
    if (isRecord) {
      for (let current = depth; current > 0; current--) yield* c.promote(node);
      return;
    }
    if (depth <= target) return;
    if (depth === target + 1) { yield* c.promote(node); return; }
    for (let current = depth; current > target + 2; current--) {
      c.visit();
      yield* c.event('visit', `Inspect ancestor ${c.key(node)}`, 'Walk to the sampled repair level before rotating.', node);
      node = c.parent(node);
    }
    c.visit();
    const parent = c.parent(node), grand = c.parent(parent);
    if ((c.left(parent) === node) === (c.left(grand) === parent)) yield* c.promote(parent);
    else { yield* c.promote(node); yield* c.promote(node); }
  };
});
