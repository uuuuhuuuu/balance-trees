// Leaf spacing keeps long one-child paths narrow. All work is bounded by view size.
export function treeLayout(frame, keys, compact = false) {
  const nodes = new Map(frame.nodes.map(node => [node.key, node]));
  const ranks = new Map([...new Set(keys)].sort((a, b) => a - b).map((key, index) => [key, index]));
  const result = new Map(), stack = frame.root === null ? [] : [[frame.root, 0, false]];
  let leaf = 0;
  while (stack.length) {
    const [key, depth, visited] = stack.pop(), node = nodes.get(key);
    if (!visited) {
      stack.push([key, depth, true]);
      if (node.right !== null) stack.push([node.right, depth + 1, false]);
      if (node.left !== null) stack.push([node.left, depth + 1, false]);
    } else {
      const children = [node.left, node.right].filter(key => key !== null);
      const x = compact ? (children.length ? children.reduce((sum, key) => sum + result.get(key).x, 0) / children.length : leaf++ * 62) : ranks.get(key) * 76;
      result.set(key, { x, y: depth * (compact ? 68 : 90) });
    }
  }
  return result;
}
