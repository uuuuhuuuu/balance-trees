# Random-level policies: investigation and version 2

`random-level` keeps the original interval-to-depth policy and its recorded
results. `random-level-v2` is a separate policy that uses the same random level
sampler but changes how it repairs the tree. Both are available in the Python
CLI, factory, visualizer and browser worker.

The separate [policy and reports webpage](../src/balance_trees/showcase/site/dist/random-level-v2.html)
is served at `/random-level-v2.html`. It includes the description, expected
rotation proof, paired workload charts with log₂(n) guides, measurement tables,
and downloads. Links from the visualizer and the three earlier reports lead
to it. The original pages and their data remain available.

## Why rotations grow in the original policy

Let `k` be the number of previous successful insertions and `h` the new leaf's
initial depth. The original policy draws 64 fair bits and maps the value into
the **previous** observed priority interval. It divides that interval into
bands proportional to `1, 2, 4, ...`, using `k.bit_length()` levels. Its sampled
target `t` is therefore usually near `log₂(k)`.

It then repeatedly promotes the **inserted leaf**, costing exactly
`max(0, h - t)` primitive rotations. This is not a treap insertion: no persistent
heap of priorities determines when promotions stop. A perfect-tree level
profile does not model the depths of the actual tree or the priorities along
the insertion path. If `h` outgrows the sampled target, so does rotation work.

The preserved five-trial random-order results show the effect:

| Keys | Mean initial insertion depth | Rotations per insertion |
| ---: | ---: | ---: |
| 1,000 | 11.105 | 4.230 |
| 16,000 | 16.338 | 5.478 |
| 128,000 | 20.748 | 6.867 |

These are finite measurements, not a proof of a logarithmic asymptote. The
implementation nevertheless has no constant expected-rotation argument.
Changing a plot, scaling the target by a fitted constant, or truncating leaf
promotions would not establish the desired behavior.

## Version 2 policy

Version 2 retains the original sampler, external count and priority extrema.
For each successful insertion:

1. Insert a leaf using ordinary BST search; record its initial depth `h`.
2. Draw a fresh 64-bit priority and sample `t` from the previous interval.
3. Update the count and extrema after sampling.
4. If the priority is a **strict new minimum**, promote the inserted leaf all
   the way to the root. This is the only case that can exceed two rotations.
5. Otherwise, if `h <= t`, do nothing. A strict new maximum has `t = h`, so it
   stays a leaf.
6. If `h = t + 1`, promote the leaf once.
7. Otherwise walk up, without rotating, to the ancestor `v` at depth `t + 2`.
   Repair its two-edge path:
   - For two left edges or two right edges, promote `v.parent` once.
   - For a left-right or right-left bend, promote `v` twice.

The repaired subtree's root reaches depth `t`; the inserted leaf need not reach
that level. Subtrees move with the repair. Version 2 is consequently a new
policy, not an optimization that promises the original tree shapes.

The local straight/bent rule reuses the repository's `ZigZag` primitive from
[Brodal, Algorithm 2](https://arxiv.org/html/2404.08287v1#S3). Choosing its location
by interval bands and retaining record-minimum promotions are this version's
design; Brodal's balance results do not transfer to it.

Equal priorities are **not** strict records. Even when the previous extrema
are equal and the sampler returns zero, an equal roll uses the bounded local
repair. Duplicate keys use no bits, rotations or state updates.

## Expected rotation bound

Assume an initially empty tree and independent uniformly distributed priority
rolls for successful insertions. With `k` previous insertions:

- The initial depth is at most `k`.
- A strict new minimum among `k + 1` iid rolls has probability at most
  `1 / (k + 1)`. Exchangeability gives this bound; finite-priority ties can
  only reduce the probability of a unique minimum.
- Every non-record insertion uses at most two rotations.

Writing `A` for the strict-record event, a pointwise upper bound is

```text
R <= 2 + k * 1[A]
E[R] <= 2 + k * P(A) <= 2 + k/(k+1) < 3.
```

The first insertion uses zero rotations. Linearity of expectation also gives
expected total rotations below `3n` for any fixed sequence of `n` distinct keys.
Independence between tree depth and the record event is not needed: `h <= k`
holds for every history.

This is an expectation **over the whole random priority history**. It is not
a bound conditioned on every possible existing tree and set of extrema. An
individual record insertion can use `h` rotations, so neither the maximum
rotations nor every finite sample average is guaranteed to be below three.
Injecting a prepopulated tree with a fresh, inconsistent policy state does not
meet the initially-empty-tree assumption.

## Costs and limitations

| Property | Original `random-level` | `random-level-v2` |
| --- | --- | --- |
| Repair location | Repeatedly promote the new leaf to `t` | Repair a local path at `t`; promote the leaf fully only on a strict record |
| Ordinary insertion rotations | Up to `h` | At most two |
| Strict new-minimum rotations | `h` | `h` |
| Expected rotations | No constant bound established | Fewer than three from empty under iid uniform rolls |
| Fair bits per successful insertion | Exactly 64 | Exactly 64 |
| Persistent state | Count and two priority extrema outside nodes | Same |
| Worst-case ancestor traversal | No separate walk | Up to `h` pointer steps |
| Expected logarithmic depth | Unproved | Unproved |

Small expected rotation counts do not imply constant rebalancing time. Version
2 can spend `O(h)` walking to its repair, in addition to `O(log k)` integer band
iterations and the initial BST search. Its `visits` metric counts those walked
nodes and the selected two-edge repair inspection; rotations are counted
separately. It performs no subtree recount scans and stores no priorities or
sizes in nodes. Rotation distances can now be positive, because the promoted
node can be an ancestor of the inserted leaf.

This remains a heuristic for tree depth and height. It does not preserve a
treap priority heap or the exact random-BST distribution. Making promotions
geometric relative to the leaf or simply stopping after one rotation made
converging inputs much deeper in exploratory checks; those alternatives are
not the implemented policy. The two-edge repair is tested on all seven input
families, but these checks do not prove logarithmic expected depth.

## Run and compare the versions

```sh
# Select either version explicitly; both use the same factory and trace API.
PYTHONPATH=src python3 -m balance_trees.demo --strategy random-level --keys 1 10 2 9 3 8 --seed 2026
PYTHONPATH=src python3 -m balance_trees.demo --strategy random-level-v2 --keys 1 10 2 9 3 8 --seed 2026
PYTHONPATH=src python3 -m balance_trees.showcase --port 8000

# A fresh output directory preserves prior runs. Both versions get paired seeds.
PYTHONPATH=src python3 -m balance_trees.benchmark \
  --sizes 1000 16000 128000 --trials 3 --seed 2026 --timeout 10 \
  --strategies random-level random-level-v2 \
  --output benchmarks/results/my-random-level-comparison

# Generate comparison pages separately from the preserved published results.
PYTHONPATH=src python3 -m balance_trees.benchmark_report \
  --input benchmarks/results/my-random-level-comparison \
  --output benchmarks/results/my-random-level-comparison/site
```

In Python use `TreeFlavor.create("random-level-v2", seed=2026)` or construct
`RandomLevelV2()` directly. `TreapPriority` and `random-level` retain their
original meanings. The browser's two versions share the original BigInt band
sampler; both engines register them independently. Browser and Python PRNGs
differ, so equal numeric seeds do not imply identical priorities or shapes.
Tests also feed identical 64-bit streams to Python and the browser worker to
check exact policy agreement, including ties and extreme values.

## Recorded comparison

The v2 validation completed all 63 requested trials: three sizes (1,000,
16,000 and 128,000 keys), seven input families, three trials and seed 2026.
Every completed tree passed the standard structural checks. The original
dataset already contains matching trials, so the comparison selects its first
three trial indices at each of those sizes and pairs the exact input and
rotation seeds with v2. The earlier five-trial diagnostic table above uses
all original trials; this comparison uses three per version.

On random input, mean rotations per insertion (± one standard error):

| Keys | Original `random-level` | `random-level-v2` |
| ---: | ---: | ---: |
| 1,000 | 4.506 ± 0.254 | 1.182 ± 0.033 |
| 16,000 | 5.417 ± 0.046 | 1.230 ± 0.008 |
| 128,000 | 7.090 ± 0.215 | 1.260 ± 0.012 |

At 128,000 keys, across every input family:

| Input | Original rot/key | v2 rot/key | Original mean depth | v2 mean depth | Original mean height | v2 mean height |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Random | 7.090 | 1.260 | 21.466 | 18.932 | 41.333 | 35.000 |
| Increasing | 1.000 | 1.000 | 27.223 | 22.140 | 57.000 | 52.000 |
| Decreasing | 1.000 | 1.000 | 26.984 | 22.364 | 56.333 | 49.333 |
| Converging | 1.937 | 1.724 | 26.775 | 23.442 | 79.000 | 68.667 |
| Pairs | 1.317 | 1.158 | 26.761 | 22.617 | 54.667 | 49.333 |
| Bitonic | 4.494 | 1.186 | 22.452 | 20.294 | 47.000 | 42.333 |
| Runs | 5.055 | 1.164 | 21.812 | 20.187 | 47.667 | 45.000 |

Depth and height count edges. V2 did not trade lower rotation counts for deeper
trees in these measurements. This is a limited empirical comparison, not a
general guarantee about depth or height. The runs happened in separate batches;
the comparison makes no claim about relative elapsed time.

The tracked validation artifacts are:

- [Paired operation-count and shape summaries](../benchmarks/random-level-v2/comparison.csv).
- [Pairing rules and original dataset checksum](../benchmarks/random-level-v2/comparison-config.json).
- [Every v2 trial](../benchmarks/random-level-v2/trials.csv),
  [v2 group summaries](../benchmarks/random-level-v2/summary.csv) and
  [machine, seeds and methodology](../benchmarks/random-level-v2/config.json).

Reproduce the v2 batch alone with the benchmark command above using
`--strategies random-level-v2`; retain both names to rerun the full paired
comparison. Existing published measurements and graphs are unchanged; these
validation artifacts document the separate version.

Regenerate the dedicated webpage from the tracked validation artifacts:

```sh
PYTHONPATH=src python3 -m balance_trees.random_level_report \
  --input benchmarks/random-level-v2 \
  --baseline src/balance_trees/showcase/site/dist/random-level-results/results.json \
  --description docs/random-level-v2.md \
  --output src/balance_trees/showcase/site/dist
PYTHONPATH=src python3 -m balance_trees.showcase.build --output _site
```

The generator verifies the baseline checksum and pairs raw trials by workload,
size, trial index, input seed and rotation seed. It regenerates the statistics
from those records. Only the new page, its `random-level-v2-results/` assets,
shared styling and navigation links are written; the older measurements and
graphs are preserved. The report's downloads and SVGs use relative URLs and
enter the ordinary GitHub Pages build. The workload selector enhances a page
whose complete results also remain readable without JavaScript.

## Validation

Regression checks cover the original archived measurements; straight, bent,
shallow, record and equal-priority repairs; empty trees, lookup and duplicates;
bit counts and isolated state; and invariants across all input families.
An exhaustive finite model enumerates every six-roll history from a four-value
priority domain for increasing and converging inputs, including ties, and
checks the expected-rotation bound at each insertion. Existing permutation
tests apply to both registered versions. Deletion is outside this repository's
insertion-only experiment.

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
node tests/test_showcase_browser.mjs
node tests/test_large_showcase.mjs
```
