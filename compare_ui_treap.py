import csv
import json
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from balance_trees import TreeFlavor
from balance_trees.sequences import insertion_order
from balance_trees.strategies import create_strategy

ROOT = Path(__file__).resolve().parent
N, SEED = 200000, 2026
keys = list(insertion_order('random', N, SEED))
js = r'''
import { LargeTree } from './src/balance_trees/showcase/site/dist/large-model.mjs';
let text = '';
for await (const chunk of process.stdin) text += chunk;
const {keys, seed} = JSON.parse(text);
const tree = new LargeTree({strategy: 'treap', sequence: keys, seed});
const depths = [];
while (tree.advance()) {
  if (tree.current.kind === 'insert') {
    let id = tree.focusId, depth = 0;
    while (tree.parent[id] >= 0) { id = tree.parent[id]; depth++; }
    depths.push(depth);
  }
}
if (tree.length !== keys.length || depths.length !== keys.length) throw new Error('Missing insertions');
for (let id = 0; id < tree.length; id++) {
  const p = tree.parent[id];
  if (p >= 0 && tree.higher(id, p)) throw new Error('Treap heap violation');
}
process.stdout.write(JSON.stringify(depths));
'''
print('Measuring existing UI treap...', flush=True)
process = subprocess.run(['node', '--input-type=module', '-e', js], cwd=ROOT, input=json.dumps({'keys': keys, 'seed': SEED}), text=True, capture_output=True)
if process.returncode:
    raise RuntimeError(process.stderr)
treap = json.loads(process.stdout)
print('Measuring v2.1...', flush=True)
flavor = TreeFlavor(create_strategy('random-level-v2-1'), seed=SEED)
v21 = []
for key in keys:
    stats = flavor.insert(key)
    assert stats.inserted
    v21.append(stats.insertion_depth)
assert set(flavor.tree.depths()) == set(keys)
out = ROOT / 'benchmarks/results/ui-treap-v21'
out.mkdir(parents=True, exist_ok=True)
with (out / 'depths.csv').open('w', newline='', encoding='utf-8') as handle:
    writer = csv.writer(handle)
    writer.writerow(['insertion', 'key', 'ui_treap_before_balance', 'v21_before_balance'])
    writer.writerows((i + 1, key, a, b) for i, (key, a, b) in enumerate(zip(keys, treap, v21)))
fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
for label, depths in [('UI Treap', treap), ('v2.1', v21)]:
    axes[0].plot(range(1, N + 1), depths, label=label, linewidth=0.4, alpha=0.5)
    ends = list(range(1000, N + 1, 1000))
    means = [sum(depths[end-1000:end]) / 1000 for end in ends]
    axes[1].plot(ends, means, label=label)
    print(f'{label}: mean={sum(depths)/N:.3f}, max={max(depths)}')
axes[0].set_title('Insertion depth BEFORE balancing: existing UI Treap vs v2.1')
axes[0].set_ylabel('Individual insertion depth')
axes[1].set_ylabel('Mean depth per 1,000 insertions')
axes[1].set_xlabel('Insertion number')
for ax in axes:
    ax.legend()
    ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(out / 'comparison.png', dpi=160)
plt.close(fig)
print(f'Results: {out}')
