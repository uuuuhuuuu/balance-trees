// Browser reference adapter. Python implementations emit this same trace schema.
export const MAX_KEYS = 64;
export const FLAVORS = {
  treap: { name: 'Treap', tag: 'Priority heap', note: 'A BST by key, a min-heap by random priority. Rotate the new node upward until both orders hold. Priorities are extra balance information.' },
  halving: { name: 'Halving walk', tag: 'Local randomized rule', note: 'Try a rotation with probability ½, then ¼, then ⅛… Continue from the current parent after either outcome. A success skips the demoted old parent.' },
  'constant-half': { name: 'Constant ½', tag: 'Full upward walk', note: 'Try the same ½ rotation probability at every visited node. Continue to the root after success and failure. Rotation cost can grow with insertion depth.' },
  'inverse-depth': { name: 'Inverse depth', tag: 'Depth-informed rule', note: 'Freeze the new leaf’s initial depth h, then use 1/h at every decision. Root insertion needs no coin. On sorted input, depth-one insertions rotate with certainty and create a chain.' },
  none: { name: 'Plain BST', tag: 'No rebalancing', note: 'Follow key comparisons to an empty child and insert a leaf. Ordered input exposes how a BST can become a chain.' },
  'paper-zig': { name: 'Paper · Zig', tag: 'Geometric stop', note: 'Continue upward with probability ½. On the first other outcome, promote the current node once and stop.' },
  'paper-zigzag': { name: 'Paper · ZigZag', tag: 'Geometric stop', note: 'Continue upward with probability ¾. At the first rebalance, a straight path promotes the parent once; a bent path promotes the current node twice. Requires two ancestors.' },
};
export const ORDERS = {
  increasing: 'Increasing', random: 'Random permutation', converging: 'Converging',
  decreasing: 'Decreasing', pairs: 'Pairs', bitonic: 'Bitonic', runs: 'Runs', custom: 'Custom sequence',
};

export function parseSequence(text) {
  if (typeof text !== 'string' || !text.trim()) throw new Error('Enter comma-separated integers, for example 8, 4, 12, 2.');
  const parts = text.split(',');
  if (parts.length > MAX_KEYS) throw new Error(`Use at most ${MAX_KEYS} keys for a readable animation.`);
  return parts.map((part, index) => {
    const token = part.trim();
    if (!/^[+-]?[0-9]+$/.test(token)) throw new Error(`Item ${index + 1} is not an integer. Separate every number with a comma.`);
    const value = Number(token);
    if (!Number.isSafeInteger(value)) throw new Error(`Item ${index + 1} is outside the browser’s safe integer range.`);
    return value;
  });
}

function randomGenerator(seed) {
  let state = (seed >>> 0) || 0x9e3779b9;
  return () => {
    state ^= state << 13; state ^= state >>> 17; state ^= state << 5;
    return state >>> 0;
  };
}

export function makeSequence(order, count, seed) {
  if (!Number.isInteger(count) || count < 1 || count > MAX_KEYS || !(order in ORDERS) || order === 'custom') throw new Error('Choose a preset and between 1 and 64 keys.');
  const values = Array.from({ length: count }, (_, i) => i + 1);
  if (order === 'increasing') return values;
  if (order === 'decreasing') return values.reverse();
  if (order === 'random') {
    const random = randomGenerator(seed);
    for (let i = values.length - 1; i > 0; i--) {
      const j = random() % (i + 1); [values[i], values[j]] = [values[j], values[i]];
    }
    return values;
  }
  if (order === 'converging') {
    const result = [];
    for (let low = 1, high = count; low <= high; low++, high--) {
      result.push(low); if (low !== high) result.push(high);
    }
    return result;
  }
  const evens = values.filter(x => x % 2 === 0), odds = values.filter(x => x % 2 === 1);
  if (order === 'pairs') return odds.flatMap(x => x < count ? [x + 1, x] : [x]);
  return evens.concat(order === 'bitonic' ? odds.reverse() : odds);
}

export function simulate(sequence, strategy = 'treap', seed = 2026) {
  if (!Array.isArray(sequence) || !sequence.length || sequence.length > MAX_KEYS || sequence.some(x => !Number.isSafeInteger(x))) throw new Error('Use 1 to 64 safe integer keys.');
  if (!Object.hasOwn(FLAVORS, strategy)) throw new Error('Unknown strategy.');
  if (!Number.isInteger(seed) || seed < 0 || seed > 4294967295) throw new Error('Seed must be an integer from 0 to 4294967295.');
  let root = null, insertion = 0, key = null, rotations = 0, visits = 0, bits = 0, insertionRotations = 0;
  const frames = [], priorities = new Map(), random = randomGenerator(seed);
  const bit = () => { bits++; return random() & 1; };
  function coin(numerator, denominator) {
    let remainder = BigInt(numerator), divisor = BigInt(denominator);
    if (remainder === 0n) return false;
    if (remainder === divisor) return true;
    while (true) {
      const doubled = 2n * remainder, threshold = Number(doubled / divisor);
      remainder = doubled % divisor;
      const sample = bit();
      if (sample !== threshold) return sample < threshold;
      if (remainder === 0n) return false;
    }
  }
  function capture(kind, title, description, details = {}) {
    const nodes = [], stack = root ? [[root, 0]] : [];
    let totalDepth = 0, height = 0, heapValid = true;
    while (stack.length) {
      const [node, depth] = stack.pop();
      totalDepth += depth; height = Math.max(height, depth);
      nodes.push({ key: node.key, left: node.left?.key ?? null, right: node.right?.key ?? null, priority: priorities.get(node.key) ?? null });
      for (const child of [node.left, node.right]) if (child) {
        stack.push([child, depth + 1]);
        if (strategy === 'treap' && higher(child, node)) heapValid = false;
      }
    }
    frames.push({ kind, title, description, insertion, key, root: root?.key ?? null,
      nodes: nodes.sort((a, b) => a.key - b.key), heap_valid: strategy === 'treap' ? heapValid : null,
      stats: { nodes: nodes.length, height, mean_depth: nodes.length ? totalDepth / nodes.length : 0,
        rotations, visits, random_bits: bits, insertion_rotations: insertionRotations }, ...details });
  }
  function higher(a, b) { return priorities.get(a.key) < priorities.get(b.key) || (priorities.get(a.key) === priorities.get(b.key) && a.key < b.key); }
  function promote(node) {
    const parent = node.parent, grandparent = parent.parent;
    const direction = parent.left === node ? 'right' : 'left';
    const middle = direction === 'right' ? node.right : node.left;
    const details = { focus: node.key, promoted: node.key, demoted: parent.key, middle: middle?.key ?? null, direction };
    capture('prepare', `Prepare a ${direction} rotation`, `Promote ${node.key} over ${parent.key}; the middle subtree keeps its key order.`, details);
    if (direction === 'right') { parent.left = node.right; if (node.right) node.right.parent = parent; node.right = parent; }
    else { parent.right = node.left; if (node.left) node.left.parent = parent; node.left = parent; }
    parent.parent = node; node.parent = grandparent;
    if (!grandparent) root = node;
    else if (grandparent.left === parent) grandparent.left = node;
    else grandparent.right = node;
    rotations++; insertionRotations++;
    capture('rotate', `Rotate ${direction}: ${node.key} moves up`, `${parent.key} moves down. BST ordering is preserved while the links change.`, details);
  }
  function choose(node, numerator, denominator, purpose = 'rotate') {
    visits++;
    const outcome = coin(numerator, denominator);
    const action = outcome ? purpose : purpose === 'rotate' ? 'skip rotation' : 'rebalance here';
    capture('coin', `Coin at ${node.key}: ${action}`, `Probability to ${purpose}: ${numerator}/${denominator}. ${purpose === 'rotate' ? 'The full walk continues upward after either outcome.' : 'This policy stops at its first rebalance.'}`,
      { focus: node.key, numerator: String(numerator), denominator: String(denominator), outcome, purpose });
    return outcome;
  }
  capture('ready', 'A tree starts with one decision', 'Follow the search path, insert a leaf, then watch each rotation.');
  for (let index = 0; index < sequence.length; index++) {
    insertion = index + 1; key = sequence[index]; insertionRotations = 0;
    capture('begin', `Insert ${key}`, 'Start at the root and follow the binary search rule.', { focus: key });
    let current = root, parent = null, depth = 0;
    while (current) {
      const relation = key === current.key ? 'equal to' : key < current.key ? 'smaller than' : 'larger than';
      capture('compare', `Compare ${key} with ${current.key}`, `${key} is ${relation} ${current.key}. ${key === current.key ? 'Skip this duplicate.' : key < current.key ? 'Continue left.' : 'Continue right.'}`, { focus: current.key });
      if (key === current.key) break;
      parent = current; current = key < current.key ? current.left : current.right; depth++;
    }
    if (current) {
      capture('duplicate', `${key} is already present`, 'Duplicate insertions leave the tree and random stream unchanged.', { focus: key });
    } else {
      const leaf = { key, left: null, right: null, parent };
      if (!parent) root = leaf;
      else if (key < parent.key) parent.left = leaf;
      else parent.right = leaf;
      if (strategy === 'treap') { priorities.set(key, random()); bits += 32; }
      capture('insert', `Place ${key} as a leaf`, `The search ends at depth ${depth}. Now apply the selected balancing rule.`, { focus: key });
      if (strategy === 'treap') {
        while (leaf.parent) {
          visits++;
          const violation = higher(leaf, leaf.parent);
          capture('priority', `Compare priorities: ${leaf.key} and ${leaf.parent.key}`, `Smaller priorities belong higher in this min-heap. ${violation ? 'Rotate this child up.' : 'The heap order holds; stop.'}`, { focus: leaf.key, demoted: leaf.parent.key });
          if (!violation) break;
          promote(leaf);
        }
      } else if (['halving', 'constant-half', 'inverse-depth'].includes(strategy)) {
        let node = leaf, denominator = strategy === 'constant-half' ? 2n : strategy === 'inverse-depth' ? BigInt(depth) : 2n;
        while (node.parent) {
          if (choose(node, 1n, denominator)) promote(node);
          node = node.parent;
          if (!node) break;
          if (strategy === 'halving') denominator *= 2n;
        }
      } else if (strategy.startsWith('paper-')) {
        let node = leaf;
        while (node.parent) {
          const keepGoing = choose(node, strategy === 'paper-zig' ? 1 : 3, strategy === 'paper-zig' ? 2 : 4, 'continue');
          if (keepGoing) { node = node.parent; continue; }
          if (strategy === 'paper-zig') promote(node);
          else if (node.parent.parent) {
            if ((node.parent.left === node) === (node.parent.parent.left === node.parent)) promote(node.parent);
            else { promote(node); promote(node); }
          }
          break;
        }
      }
    }
    capture('settled', `Insertion ${insertion} complete`, `${key} is in place. The tree is ready for the next key.`, { focus: key });
  }
  return { schema_version: 1, strategy, seed, sequence: [...sequence], source: 'browser', frames };
}

export function validateTrace(trace) {
  if (!trace || trace.schema_version !== 1 || !Array.isArray(trace.sequence) || !trace.sequence.length || trace.sequence.length > MAX_KEYS || trace.sequence.some(x => !Number.isSafeInteger(x))) throw new Error('Expected a version 1 rotation trace with 1–64 integer keys.');
  if (!Array.isArray(trace.frames) || !trace.frames.length || trace.frames.length > 20000) throw new Error('Trace must have between 1 and 20,000 frames.');
  for (const frame of trace.frames) {
    if (!Array.isArray(frame.nodes) || frame.nodes.length > MAX_KEYS || typeof frame.title !== 'string' || typeof frame.description !== 'string' || typeof frame.kind !== 'string' || !Number.isInteger(frame.insertion) || frame.insertion < 0 || frame.insertion > trace.sequence.length || !frame.stats) throw new Error('Trace contains an invalid frame.');
    const nodes = new Map();
    for (const node of frame.nodes) {
      if (!Number.isSafeInteger(node.key) || nodes.has(node.key) || (node.priority !== null && (!Number.isInteger(node.priority) || node.priority < 0 || node.priority > 4294967295))) throw new Error('Trace contains an invalid node.');
      nodes.set(node.key, node);
    }
    for (const name of ['nodes', 'height', 'mean_depth', 'rotations', 'visits', 'random_bits', 'insertion_rotations']) {
      if (!Number.isFinite(frame.stats[name]) || frame.stats[name] < 0) throw new Error('Trace contains invalid statistics.');
    }
    if (frame.stats.nodes !== nodes.size) throw new Error('Trace node counts do not match its snapshots.');
    const stack = frame.root === null ? [] : [[frame.root, -Infinity, Infinity]], visited = new Set();
    while (stack.length) {
      const [key, lower, upper] = stack.pop(), node = nodes.get(key);
      if (!node || visited.has(key) || key <= lower || key >= upper) throw new Error('Trace contains a cycle, broken link, or invalid BST order.');
      visited.add(key);
      if (node.left !== null) stack.push([node.left, lower, key]);
      if (node.right !== null) stack.push([node.right, key, upper]);
    }
    if (visited.size !== nodes.size) throw new Error('Trace contains disconnected nodes.');
  }
  return trace;
}
