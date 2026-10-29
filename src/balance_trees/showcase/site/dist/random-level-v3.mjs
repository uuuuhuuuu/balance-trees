import { registerStrategy } from './strategies.mjs';

registerStrategy('random-level-v3', c => {
  let count = 0, lowest = null, highest = null;
  return function* (node, depth) {
    let priority = 0n;
    for (let bit = 0; bit < 64; bit++) priority = (priority << 1n) | BigInt(c.bit());
    const previousCount = count, previousMax = highest;
    const isRecord = lowest !== null && priority < lowest;
    count++;
    if (lowest === null || priority < lowest) lowest = priority;
    if (highest === null || priority > highest) highest = priority;
    let target = depth;
    if (isRecord) target = 0;
    else if (depth >= 2 && previousMax !== null && previousCount >= 2) {
      if (yield* c.choose(node, previousMax, 1n << 64n, 'promote-leaf')) {
        const logRatio = Math.log(depth) - Math.log(2)
          - (1 + 1e-9) * Math.log(Math.log(previousCount));
        const peak = logRatio >= 0 ? depth - 1 : 1;
        const weights = new Float64Array(depth - 1);
        const suffix = new Float64Array(depth);
        for (let level = 1; level < depth; level++) {
          weights[level - 1] = Math.exp((depth - level - peak) * logRatio);
        }
        for (let i = weights.length - 1; i >= 0; i--) suffix[i] = weights[i] + suffix[i + 1];
        target = depth - 1;
        const scale = 2 ** 53;
        for (let i = 0; i < weights.length - 1; i++) {
          const numerator = Math.min(scale, Math.max(0, Math.round(weights[i] / suffix[i] * scale)));
          if (yield* c.choose(node, numerator, scale, 'choose-final-level')) {
            target = i + 1;
            break;
          }
        }
      }
    }
    yield* c.event('target', `Target depth ${target}`,
      `Rolled ${priority}. ${isRecord ? 'A strict new minimum reaches the root.' : 'Use the previous maximum for the promotion gate and normalized depth weights for the target.'} Final depth ${target}; ${depth - target} rotations.`, node);
    for (let current = depth; current > target; current--) yield* c.promote(node);
  };
});
