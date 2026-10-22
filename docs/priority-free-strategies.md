# Treap-like balance without stored priorities

## Plan and acceptance criteria

1. Keep `Node(key, left, right, parent)` and `BST(root)` unchanged. Permit temporary
   insertion variables and stacks; discard them when the insertion returns.
2. Implement an exact distribution reference before optimizing its cost.
3. Compare a bounded local approximation and a recomputed-priority alternative.
4. Measure depth, worst-key mean depth, height, decisions, rotations, logical
   random bits, and actual recount scans. Check several sizes and all seven
   input families, including converging and pairs.
5. Expose each strategy in the Python CLI, detailed visualizer, and large-run
   worker. Test exact probabilities, budgets, invariants, and engine agreement.

This plan is implemented. It explores tradeoffs; it does not claim to satisfy all
seven original requirements simultaneously. Brodal's paper proves that its two
constant-work local rules have simple bad input sequences, and discusses
Seidel's metadata-free algorithm with expected O(log² n) insertion time.
Our transparent recount reference below is a different, slower implementation.
[Source: Brodal, sections 1.2–1.3](https://arxiv.org/pdf/2404.08287).

## 1. `recount-root`: exact root lottery

After ordinary leaf insertion, walk toward the root. At each ancestor, reconstruct
its subtree's **post-insertion** size `s` and toss an exact `1/s` coin. Keep the
highest ancestor whose coin succeeds. Finally promote the inserted leaf until
it occupies that ancestor's old position. With no successes, leave it as a leaf.

Counts are assembled incrementally: start with the new leaf's size 1; add each
parent and its off-path sibling subtree. These sibling subtrees are disjoint,
so a complete pass inspects each existing node exactly once. Temporary counts
are never attached to nodes or retained in a table.

Why this is exact: randomized root insertion chooses the new key as the root of
a subtree of old size `s-1` with probability `1/s`; otherwise it descends. Our
bottom-up independent coins choose the same highest success as that top-down
process. Delaying all rotations prevents lower candidates from changing the
sizes used by later decisions. From an empty tree, induction gives a uniform
root within every key interval and independent random-BST subtrees—the same
marginal shape distribution as a treap with independent continuous priorities.
It does not reproduce a particular treap's seed or its correlated update history.
See [randomized BST background in Open Data Structures](https://opendatastructures.org/newhtml/ods/latex/rbs.html).

For any fixed insertion order, the resulting random-BST process gives expected
O(log n) depth per key and expected O(1) rotations per insertion. **Recounting
still costs Θ(n) structural inspections per insertion**, or Θ(n²) to build a
whole tree. There are `h` decisions, expected O(h) fair bits, and up to `h`
rotations, where `h` is the initial insertion depth. Temporary DFS storage is
O(tree height). Constant expected rotations is a distributional statement over
the process, not a bound conditioned on every possible current tree shape.

Use this as the correctness/quality reference for modest runs. It relaxes
constant rebalancing work, constant random-bit use, and strict local information.

## 2. `window-root`: bounded local root lottery

Use the same procedure, but stop after **64 actual node inspections**. If a
sibling count is incomplete, discard that ancestor's candidate; retain any
already selected lower candidate. Never use a guessed denominator.

This gives at most 64 inspections and 63 rotations per insertion, and expected
O(64) coin work/bits. All inspected structure is within a bounded neighborhood
of the insertion. Initial BST search remains additional work. There is **no
proven logarithmic-depth or exact-distribution guarantee**. Capping the scan
removes opportunities to repair high ancestors.

The Python strategy is configurable: `WindowRoot(budget=256)`. The registry and
browser use 64 so benchmark and visual behavior agree. A budget covering the
entire tree exactly matches `recount-root` with the same random stream.

## 3. `hash-priority`: recompute rather than remember

Define `priority(key) = SplitMix64(key XOR seed)`, using 64-bit modular arithmetic.
Compute the inserted key's priority once, recompute each encountered parent's
priority, and promote while `(priority, key)` violates heap order. Discard these
numbers afterward. The same key/seed always yields the same number, preserving
heap consistency across insertions without any priority fields or priority map.
The [public-domain SplitMix64 mixer](https://xorshift.di.unimi.it/splitmix64.c)
is implemented identically in Python and browser JavaScript.

The one seed is **external flavor configuration**, not node metadata. No fresh
fair bits are consumed during insertion; seed entropy is not free or counted
as insertion-time bits. Keys congruent modulo 2⁶⁴ collide; full keys break ties.

Under an ideal independent-hash model, this behaves like a treap. This concrete
finite mixer is **not** such a model, so logarithmic depth and constant expected
rotations are empirical expectations here, not guarantees. Known seeds or
adversarial keys can defeat it. It also relaxes the original structural-only
locality requirement by using key-derived information.

Assigning unrelated fresh random priorities to ancestors on every insertion
would lose this consistency. Temporary numbers need either a reproducible rule
(as here) or a distribution justified by the current structure (the root lottery).

## Comparison with the original requirements

| Property | Recount root | Window root | Recomputed priority |
| --- | --- | --- | --- |
| Extra fields in a node/tree | None | None | None |
| External persistent configuration | RNG seed | RNG seed, fixed budget | One fixed seed |
| Rotations | Expected O(1); up to `h` | At most 63 | Up to `h`; mixer-dependent |
| Rebalance work beyond search | Θ(n) scans + coins/rotations | Expected O(64) | Rehash comparisons + rotations |
| Local structure only | Full-tree reconstruction | Bounded neighborhood | Uses key-derived priorities |
| Fresh fair bits per insertion | Expected O(h) | Expected O(64) | Zero; external seed retained |
| Expected logarithmic depth | Exact random-BST distribution | Unproved | Unproved for this mixer |

Existing rotation-distance CSVs measure the original identity of the promoted
node. New strategies repeatedly promote the inserted node, so those distances
are zero even if it travels far upward. Use rotation counts to assess that
travel; zero recorded distance is not evidence that every rotation stays near
the leaf's original location.

## Experiment and results

Reproduce the completed **2,268 trials** (nine strategies × seven families ×
three sizes × twelve independent seeds):

```sh
PYTHONPATH=src python -m balance_trees.experiment \
  --sizes 64 256 1024 --trials 12 --seed 2026 \
  --output benchmarks/results/priority-free-new --progress
```

The output directory must be new. The completed local run is under
`benchmarks/results/priority-free-20261022/`, with text/Markdown reports, CSVs,
per-key uncertainty, and complete seed/configuration metadata. Random permutations
are fixed within each size; SE measures trial seed variation. These are operation
counts and depth measurements, not elapsed-time benchmarks.

At `n=1024`, average final node depth (mean ± SE):

| Input | Halving | Paper ZigZag | Recount root | Window root (64) | Recomputed priority |
| --- | ---: | ---: | ---: | ---: | ---: |
| Increasing | 22.71 ± 2.22 | 11.75 ± 0.22 | 10.90 ± 0.19 | 19.40 ± 0.54 | 11.13 ± 0.20 |
| Converging | 346.89 ± 2.34 | 11.16 ± 0.15 | 10.92 ± 0.16 | 33.04 ± 0.79 | 10.89 ± 0.16 |
| Pairs | 36.75 ± 3.15 | 69.42 ± 1.98 | 10.84 ± 0.10 | 21.58 ± 0.69 | 11.13 ± 0.24 |
| Random | 17.47 ± 0.86 | 11.93 ± 0.38 | 11.06 ± 0.14 | 10.95 ± 0.18 | 11.24 ± 0.25 |

Across all seven families at this size, recount averaged 512.5 scans per
insertion; the capped version averaged 62.03. The recomputed-priority version
needed no recount scans. Recount and recomputed-priority mean rotations ranged
from approximately 0.99 to 1.97. Observed maxima are not theoretical bounds.

**Decision:** use recount as the exact metadata-free research reference, and
recomputed priority for practical large visual demonstrations when a fixed
external seed is acceptable. Keep the window strategy as an explicitly weaker
local experiment. These finite results do not establish asymptotic bounds for
any heuristic.

## Implementation and validation

`strategies/lottery.py` shares recount/capped logic; `strategies/hashed.py` contains
the recomputed mixer. `RebalanceContext.scan()` and `compare_priority()` expose
work to statistics and trace recording. `priority-free.mjs` shares lottery
logic between detailed and worker browser models; cached visualization subtree
sizes are deliberately not read by the lottery.

Tests exhaustively check the exact shape probabilities for small key sets,
including all insertion permutations through four keys; bound inspections and
rotations for capped runs; check duplicate behavior, incomplete counts, signed
keys, collisions, stable heap order, and Python/JavaScript priority parity.
Both new and existing strategies are covered by invariant and model-agreement
tests. A separate one-million-key random run of the recomputed-priority browser
engine finished with height 49 and mean depth 23.736643, no priority array, and
no fresh insertion bits. This is a functional demonstration, not a bound or a
performance comparison. The visualizer shows recount scans, candidate coins, recomputed priority
comparisons, and primitive rotations in its clickable event timeline.
