// No priority table: these numbers exist only during a comparison.
// SplitMix64 mixer (public domain): https://xorshift.di.unimi.it/splitmix64.c
const MASK64 = (1n << 64n) - 1n;
export function hashPriority(key, seed) {
  let value = ((BigInt(key) ^ BigInt(seed)) + 0x9e3779b97f4a7c15n) & MASK64;
  value = ((value ^ (value >> 30n)) * 0xbf58476d1ce4e5b9n) & MASK64;
  value = ((value ^ (value >> 27n)) * 0x94d049bb133111ebn) & MASK64;
  return value ^ (value >> 31n);
}

// Shared by the full-history model and the typed-array worker. The adapter's
// scan/choose/promote generators expose every operation to the existing player.
export function* rootLottery(leaf, adapter, budget = Infinity) {
  yield* adapter.scan(leaf);
  let child = leaf, size = 1, selected = null, used = 1;
  while (adapter.parent(child) !== null) {
    if (used === budget) break;
    const parent = adapter.parent(child);
    yield* adapter.scan(parent); used++;
    const sibling = adapter.left(parent) === child ? adapter.right(parent) : adapter.left(parent);
    const stack = sibling === null ? [] : [sibling];
    let siblingSize = 0;
    while (stack.length) {
      if (used === budget) break;
      const node = stack.pop();
      yield* adapter.scan(node); used++; siblingSize++;
      const left = adapter.left(node), right = adapter.right(node);
      if (right !== null) stack.push(right);
      if (left !== null) stack.push(left);
    }
    if (stack.length) break;
    size += 1 + siblingSize;
    if (yield* adapter.choose(parent, 1, size, 'select-root')) selected = parent;
    child = parent;
  }
  if (selected !== null) {
    const boundary = adapter.parent(selected);
    while (adapter.parent(leaf) !== boundary) yield* adapter.promote(leaf);
  }
}
