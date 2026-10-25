import { createStrategy } from './strategies.mjs';
// Bounded-memory reference engine for large visual runs. No history is retained.
// Typed-array metadata accelerates display statistics; this is not benchmark code.
import { randomGenerator } from './model.mjs';

export const DETAIL_LIMIT = 128;
export const VISIBLE_LIMIT = 48;
export const VISIBLE_DEPTH = 8;

export function createSequence({ order, count, seed, sequence, text }) {
  if (text !== undefined) {
    if (!String(text).trim()) throw new Error('Enter comma-separated integers.');
    let entries = 1;
    for (const char of String(text)) if (char === ',') entries++;
    if (entries * 84 > 512 * 1024 * 1024) throw new Error('This CSV would exceed the 512 MiB working-memory budget. Try fewer keys.');
    const fields = String(text).split(',');
    const values = new Float64Array(fields.length);
    fields.forEach((field, index) => {
      const token = field.trim();
      if (!/^[+-]?[0-9]+$/.test(token) || !Number.isSafeInteger(Number(token))) throw new Error(`Item ${index + 1} must be a safe integer.`);
      values[index] = Number(token);
    });
    return { count: values.length, at: index => values[index], order: 'custom' };
  }
  if (sequence) return { count: sequence.length, at: index => sequence[index], order: 'custom' };
  if (!Number.isSafeInteger(count) || count < 1) throw new Error('The number of keys must be a positive integer.');
  // Node links use signed 32-bit indices. Memory limits normally apply first.
  if (count > 2147483647) throw new Error('This run exceeds the typed-array node index range.');
  if (order === 'random') {
    const values = new Int32Array(count), random = randomGenerator(seed);
    for (let i = 0; i < count; i++) values[i] = i + 1;
    for (let i = count - 1; i > 0; i--) {
      const j = random() % (i + 1); const value = values[i]; values[i] = values[j]; values[j] = value;
    }
    return { count, at: index => values[index], order };
  }
  const evens = Math.floor(count / 2);
  const generators = {
    increasing: i => i + 1,
    decreasing: i => count - i,
    converging: i => i % 2 === 0 ? i / 2 + 1 : count - Math.floor(i / 2),
    pairs: i => i % 2 ? i : Math.min(i + 2, count),
    bitonic: i => i < evens ? 2 * (i + 1) : (count % 2 ? count : count - 1) - 2 * (i - evens),
    runs: i => i < evens ? 2 * (i + 1) : 2 * (i - evens) + 1,
  };
  if (!generators[order]) throw new Error('Unknown sequence.');
  return { count, at: generators[order], order };
}

export class LargeTree {
  constructor(config) {
    const requested = config.sequence?.length ?? config.count;
    const bytesPerKey = (config.strategy === 'none' ? 36 : config.strategy === 'treap' ? 32 : 28) + (config.order === 'random' ? 4 : 0);
    if (requested * bytesPerKey > 512 * 1024 * 1024) throw new Error('This run would need more than 512 MiB of working memory. Try fewer keys.');
    this.input = createSequence(config);
    this.strategy = config.strategy; this.seed = config.seed;
    this.visibleLimit = config.visibleLimit ?? VISIBLE_LIMIT;
    this.visibleDepth = config.visibleDepth ?? VISIBLE_DEPTH;
    if (!Number.isInteger(this.visibleLimit) || this.visibleLimit < 6 || this.visibleLimit > VISIBLE_LIMIT || !Number.isInteger(this.visibleDepth) || this.visibleDepth < 1 || this.visibleDepth > VISIBLE_DEPTH) throw new Error('Invalid preview window dimensions.');
    const capacity = this.input.count;
    if (!Number.isSafeInteger(capacity) || capacity < 1 || capacity > 2147483647) throw new Error('Use a positive number of keys within the typed-array index range.');
    const estimatedBytes = capacity * (this.strategy === 'none' ? 36 : this.strategy === 'treap' ? 32 : 28)
      + (this.input.order === 'random' ? capacity * 4 : 0)
      + (this.input.order === 'custom' ? capacity * 48 : 0);
    if (estimatedBytes > 512 * 1024 * 1024) throw new Error('This run would need more than 512 MiB of working memory. Try fewer keys.');
    if (!Number.isInteger(this.seed) || this.seed < 0 || this.seed > 4294967295) throw new Error('Seed must be an integer from 0 to 4294967295.');
    try {
      this.keys = new Float64Array(capacity);
      this.left = new Int32Array(capacity).fill(-1);
      this.right = new Int32Array(capacity).fill(-1);
      this.parent = new Int32Array(capacity).fill(-1);
      this.sizes = new Uint32Array(capacity);
      this.heights = new Int32Array(capacity);
      this.priorities = this.strategy === 'treap' ? new Uint32Array(capacity) : null;
      this.depths = this.strategy === 'none' ? new Int32Array(capacity) : null;
      this.rankIds = this.strategy === 'none' && this.input.order !== 'custom' ? new Int32Array(capacity + 1) : null;
    } catch { throw new Error('Not enough browser memory for this run. Try fewer keys.'); }
    this.root = -1; this.length = 0; this.insertion = 0; this.key = null;
    this.rotations = 0; this.visits = 0; this.bits = 0; this.insertionRotations = 0;
    this.scans = 0;
    this.completeSizes = false;
    this.totalDepth = 0; this.height = 0; this.focusId = -1;
    this.heapValid = true;
    this.minimum = -1; this.maximum = -1; this.last = -1; this.lastLower = -Infinity; this.lastUpper = Infinity;
    this.random = randomGenerator(this.seed);
    this.current = this.event('ready', 'Ready', 'Play or step forward.');
    const tree = this;
    this.rebalance = createStrategy(this.strategy, {
      seed: this.seed, bit: () => { this.bits++; return this.random() & 1; },
      key: id => this.keys[id],
      parent: id => this.parent[id] < 0 ? null : this.parent[id],
      left: id => this.left[id] < 0 ? null : this.left[id],
      right: id => this.right[id] < 0 ? null : this.right[id],
      higher: (a, b) => this.higher(a, b), visit: () => this.visits++,
      event: function* (kind, title, description, id) { tree.focusId = id; yield tree.event(kind, title, description, { focus: tree.keys[id] }); },
      scan: function* (id) { tree.scans++; tree.focusId = id; yield tree.event('scan', `Count node ${tree.keys[id]}`, 'Temporary structural count; no stored subtree size is read.', { focus: tree.keys[id] }); },
      choose: (...args) => this.choose(...args), promote: id => this.promote(id),
    });
    this.iterator = this.events();
  }
  size(id) { return id < 0 ? 0 : this.sizes[id]; }
  nodeHeight(id) { return id < 0 ? -1 : this.heights[id]; }
  refresh(id) {
    this.sizes[id] = 1 + this.size(this.left[id]) + this.size(this.right[id]);
    this.heights[id] = 1 + Math.max(this.nodeHeight(this.left[id]), this.nodeHeight(this.right[id]));
  }
  refreshAncestors(id) { while (id >= 0) { this.refresh(id); id = this.parent[id]; } }
  event(kind, title, description, details = {}) {
    return { kind, title, description, insertion: this.insertion, key: this.key, ...details };
  }
  coin(numerator, denominator) {
    let remainder = BigInt(numerator); const divisor = BigInt(denominator);
    if (remainder === 0n) return false;
    if (remainder === divisor) return true;
    while (true) {
      const doubled = remainder * 2n, threshold = Number(doubled / divisor);
      remainder = doubled % divisor; this.bits++;
      const sample = this.random() & 1;
      if (sample !== threshold) return sample < threshold;
      if (remainder === 0n) return false;
    }
  }
  *choose(id, numerator, denominator, purpose = 'rotate') {
    this.focusId = id; this.visits++;
    const outcome = this.coin(numerator, denominator);
    yield this.event('coin', `Decision at ${this.keys[id]}`, `Probability to ${purpose}: ${numerator}/${denominator}. Outcome: ${outcome ? 'yes' : 'no'}.`, {
      focus: this.keys[id], numerator: String(numerator), denominator: String(denominator), outcome, purpose,
    });
    return outcome;
  }
  *promote(id) {
    const parent = this.parent[id], grandparent = this.parent[parent];
    const rightRotation = this.left[parent] === id;
    const middle = rightRotation ? this.right[id] : this.left[id];
    const details = { focus: this.keys[id], promoted: this.keys[id], demoted: this.keys[parent], middle: middle < 0 ? null : this.keys[middle], direction: rightRotation ? 'right' : 'left' };
    this.focusId = id;
    yield this.event('prepare', `Prepare a ${details.direction} rotation`, `${this.keys[id]} moves above ${this.keys[parent]}.`, details);
    this.totalDepth += rightRotation
      ? this.size(this.right[parent]) - this.size(this.left[id])
      : this.size(this.left[parent]) - this.size(this.right[id]);
    if (rightRotation) { this.left[parent] = middle; this.right[id] = parent; }
    else { this.right[parent] = middle; this.left[id] = parent; }
    if (middle >= 0) this.parent[middle] = parent;
    this.parent[parent] = id; this.parent[id] = grandparent;
    if (grandparent < 0) this.root = id;
    else if (this.left[grandparent] === parent) this.left[grandparent] = id;
    else this.right[grandparent] = id;
    this.refresh(parent); this.refresh(id); this.refreshAncestors(grandparent);
    this.height = this.heights[this.root];
    if (this.priorities) this.heapValid = this.parent[id] < 0 || !this.higher(id, this.parent[id]);
    this.rotations++; this.insertionRotations++;
    yield this.event('rotate', `Rotate ${details.direction}`, `${this.keys[id]} is promoted; ${this.keys[parent]} is demoted.`, details);
  }
  higher(id, parent) {
    return this.priorities[id] < this.priorities[parent]
      || (this.priorities[id] === this.priorities[parent] && this.keys[id] < this.keys[parent]);
  }
  fastPlainParent(key) {
    if (this.strategy !== 'none' || this.root < 0) return null;
    if (key > this.keys[this.maximum]) return { parent: this.maximum, lower: this.keys[this.maximum], upper: Infinity };
    if (key < this.keys[this.minimum]) return { parent: this.minimum, lower: -Infinity, upper: this.keys[this.minimum] };
    if (this.last >= 0 && key > this.lastLower && key < this.lastUpper && key !== this.keys[this.last]) {
      const child = key < this.keys[this.last] ? this.left[this.last] : this.right[this.last];
      if (child < 0) return { parent: this.last, lower: key < this.keys[this.last] ? this.lastLower : this.keys[this.last], upper: key < this.keys[this.last] ? this.keys[this.last] : this.lastUpper };
    }
    if (this.rankIds && key > 1 && key < this.rankIds.length - 1) {
      const before = this.rankIds[key - 1] - 1, after = this.rankIds[key + 1] - 1;
      if (before >= 0 && after >= 0 && this.rankIds[key] === 0) return { parent: this.depths[before] > this.depths[after] ? before : after, lower: key - 1, upper: key + 1 };
    }
    return null;
  }
  *events() {
    for (let index = 0; index < this.input.count; index++) {
      this.insertion = index + 1; this.key = this.input.at(index); this.insertionRotations = 0;
      if (!Number.isSafeInteger(this.key)) throw new Error(`Item ${index + 1} must be a safe integer.`);
      yield this.event('begin', `Insert ${this.key}`, 'Follow the BST key order.');
      let current = this.root, parent = -1, depth = 0, lower = -Infinity, upper = Infinity;
      const fast = this.fastPlainParent(this.key);
      if (fast) {
        ({ parent, lower, upper } = fast); depth = this.depths[parent] + 1; current = -1;
      } else {
        while (current >= 0) {
          this.focusId = current;
          yield this.event('compare', `Compare ${this.key} with ${this.keys[current]}`, this.key < this.keys[current] ? 'Continue left.' : this.key > this.keys[current] ? 'Continue right.' : 'Skip this duplicate.', { focus: this.keys[current] });
          if (this.key === this.keys[current]) break;
          parent = current;
          if (this.key < this.keys[current]) { upper = this.keys[current]; current = this.left[current]; }
          else { lower = this.keys[current]; current = this.right[current]; }
          depth++;
        }
      }
      if (current >= 0) {
        yield this.event('duplicate', `${this.key} is already present`, 'No new node or random bits are needed.', { focus: this.key });
      } else {
        const id = this.length++;
        this.keys[id] = this.key; this.parent[id] = parent; this.sizes[id] = 1;
        if (parent < 0) this.root = id;
        else if (this.key < this.keys[parent]) this.left[parent] = id;
        else this.right[parent] = id;
        this.totalDepth += depth; this.focusId = id;
        if (this.minimum < 0 || this.key < this.keys[this.minimum]) this.minimum = id;
        if (this.maximum < 0 || this.key > this.keys[this.maximum]) this.maximum = id;
        if (this.strategy === 'none') {
          this.depths[id] = depth; this.height = Math.max(this.height, depth);
          if (this.rankIds) this.rankIds[this.key] = id + 1;
          this.last = id; this.lastLower = lower; this.lastUpper = upper;
        } else { this.refreshAncestors(parent); this.height = this.heights[this.root]; }
        if (this.priorities) { this.priorities[id] = this.random(); this.bits += 32; this.heapValid = parent < 0 || !this.higher(id, parent); }
        yield this.event('insert', `Insert ${this.key} at depth ${depth}`, fast ? 'A known search boundary locates this leaf directly.' : 'The key is now a leaf.', { focus: this.key });
        yield* this.rebalance(id, depth);
      }
      yield this.event('settled', `Insertion ${this.insertion} complete`, `${this.key} is in place.`, { focus: this.key });
    }
  }
  advance() {
    const result = this.iterator.next();
    if (!result.done) this.current = result.value;
    else if (this.strategy === 'none' && !this.completeSizes) {
      // Plain BST fast insertion does not walk ancestors to maintain view sizes.
      // Children have later insertion IDs, so one reverse pass is sufficient at
      // completion. During playback, collapsed counts are explicitly unknown.
      for (let id = this.length - 1; id >= 0; id--) this.sizes[id] = 1 + this.size(this.left[id]) + this.size(this.right[id]);
      this.completeSizes = true;
    }
    return !result.done;
  }
  snapshot(limit = this.visibleLimit) {
    let anchor = this.root;
    if (this.length > limit && this.focusId >= 0) {
      anchor = this.focusId;
      for (let i = 0; i < Math.min(5, this.visibleDepth, limit - 1) && this.parent[anchor] >= 0; i++) anchor = this.parent[anchor];
    }
    const selected = new Set();
    if (anchor >= 0) {
      let id = this.focusId;
      for (let i = 0; id >= 0 && i < Math.min(6, this.visibleDepth + 1, limit); i++, id = this.parent[id]) {
        selected.add(id); if (id === anchor) break;
      }
      selected.add(anchor);
      const queue = [[anchor, 0]];
      for (let index = 0; index < queue.length && selected.size < limit; index++) {
        const [current, depth] = queue[index];
        if (this.length > limit && depth >= this.visibleDepth) continue;
        for (const child of [this.left[current], this.right[current]]) if (child >= 0) {
          if (!selected.has(child)) selected.add(child);
          queue.push([child, depth + 1]); if (selected.size >= limit) break;
        }
      }
    }
    const nodes = [...selected].map(id => ({ key: this.keys[id],
      left: selected.has(this.left[id]) ? this.keys[this.left[id]] : null,
      right: selected.has(this.right[id]) ? this.keys[this.right[id]] : null,
      priority: this.priorities ? this.priorities[id] : null,
      hidden_left: this.left[id] < 0 || selected.has(this.left[id]) ? 0 : this.strategy === 'none' && !this.completeSizes ? null : this.size(this.left[id]),
      hidden_right: this.right[id] < 0 || selected.has(this.right[id]) ? 0 : this.strategy === 'none' && !this.completeSizes ? null : this.size(this.right[id]),
    }));
    return { ...this.current, root: anchor < 0 ? null : this.keys[anchor], nodes,
      windowed: this.length > nodes.length,
      heap_valid: this.priorities ? this.heapValid : null,
      stats: { nodes: this.length, height: this.height, mean_depth: this.length ? this.totalDepth / this.length : 0,
        rotations: this.rotations, visits: this.visits, random_bits: this.bits, insertion_rotations: this.insertionRotations, scanned_nodes: this.scans },
    };
  }
}
