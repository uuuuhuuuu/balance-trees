# Local large-sequence benchmarks

Open `/results.html` for graphs or `/summary.html` for the compact static website
after launching `PYTHONPATH=src python3 -m balance_trees.showcase --port 8000`.
Both are also readable as local files. All assets and downloads live together
under `src/balance_trees/showcase/site/dist/` and enter the ordinary static build.

The recorded matrix covers every registered Python strategy: halving,
constant-half, inverse-depth, none, paper-zig, paper-zigzag, recount-root,
window-root, hash-priority and random-level. The stored-priority treap is a
browser reference, not a registered Python benchmark policy.

The included run on the AMD Ryzen 5 1600X completed **232 of 280 groups**:
**696 completed trials, 48 subprocess timeouts and 96 explicitly not-run trials**.
At 64,000 keys, constant-half, paper-zigzag, hash-priority and random-level
completed all seven input families within the deadline; recount-root completed
none at that size. These are completion results under the recorded limit, not
claims about asymptotic complexity. Every individual measurement is in the
static pages and their CSV/JSON downloads.

## Reproduce

Python 3.11+ and the standard library are sufficient. Run from the repository
root. The recorded profile requested 840 trials: ten strategies, seven orders,
four sizes (1,000 / 4,000 / 16,000 / 64,000), three trial seeds. Every output
directory must be new, so rerunning cannot erase a previous measurement.
The current default additionally includes `random-level-v2` (924 planned trials).
The recorded pages and datasets retain their original ten-strategy measurements.

```sh
PYTHONPATH=src python3 -m balance_trees.benchmark \
  --sizes 1000 4000 16000 64000 --trials 3 --seed 2026 --timeout 3 \
  --output benchmarks/results/my-large-run
PYTHONPATH=src python3 -m balance_trees.benchmark_report \
  --input benchmarks/results/my-large-run \
  --output src/balance_trees/showcase/site/dist
PYTHONPATH=src python3 -m balance_trees.showcase.build --output _site
```

For longer experiments increase `--timeout`, `--trials` and/or `--sizes`.
`--strategies` and `--orders` select subsets. Installed entry points are
`balance-tree-benchmark` and `balance-tree-benchmark-report`.

## Measurement boundaries

- Each trial runs in a new subprocess, sequentially. There are no parallel timed
  trials. A separate 32-key tree warms the interpreter before the measured tree.
- `perf_counter()` measures the instrumented insertion loop, including search,
  rebalancing, logical-bit counting and cost collection. Input generation,
  startup, warmup, final structural validation, serialization and graphs are
  excluded. This measures this Python implementation, rather than an
  uninstrumented implementation or the optimized browser worker.
- Every completed tree passes the existing ordering, parent-link, cycle and
  key-set checks. Root depth is zero. Group metrics are trial means; `max_*`
  metrics are maxima across completed trials.
- Decisions count coin sites and heap comparisons; `random-level-v2` also counts
  deterministic ancestor visits and the selected repair inspection. The target-band
  arithmetic in `random-level` is reflected in its bits, rotations and timing;
  it adds no coin-site or heap-comparison visits. Scans count actual transient
  recount inspections, separately from ordinary BST search.
- The deadline covers the whole subprocess, including startup, warmup and final
  validation. A timeout supplies no completed runtime or tree metrics. After a
  timeout/error, remaining trials for that strategy/order/size are explicitly
  `not_run`. Other groups still execute, including larger sizes.
- Graphs plot only groups with every requested trial complete. Partial metrics
  appear in the full table and downloads with their completed-trial counts.
  Missing points break lines and never become zeros. SVGs use log key counts
  horizontally and `log(1 + value)` vertically to keep exact zero costs visible.
  Whiskers show one standard error where available.
- One input permutation per size is fixed across strategies and trials. Trial
  seeds use the experiment's SHA-256 derivation. Standard errors measure
  rebalancing variation conditional on that input, not all possible random
  insertion orders or all variation in system load. Three trials are exploratory.
- CPU model, logical CPU count, platform, interpreter, UTC timestamps, seed,
  deadline and methodology are in `config.json`. Instrumentation, OS scheduling,
  interpreter and other programs on this computer affect timings. Do not infer
  general balance or complexity guarantees from the finite sample.

## All outputs

| Output | Contents |
| --- | --- |
| `trials.jsonl` | Append-only checkpoint of every attempted/not-run trial |
| `trials.csv` | Every trial, seeds, status and all measured metrics |
| `summary.csv` | Every strategy/order/size group, completed count, means and SEs |
| `results.json` | Complete metadata, summaries and raw trials |
| `config.json` | Machine and reproduction metadata |
| `results.html` | Workload-selectable graphs and measurement tables |
| `summary.html` | One compact card per strategy; largest completed size per workload, plus the complete matrix |
| `results/*.svg` | Seven metrics for every workload; downloadable standalone graphs |

The result pages never require external fonts, chart libraries or analytics.
`summary.html` works without JavaScript; the graph page shows all workloads
without JavaScript. The selector progressively filters those existing sections.

Generated raw run directories in `benchmarks/results/` stay ignored. The report's
recorded data and SVGs under `site/dist/results/` are tracked so a fresh checkout
and GitHub Pages contain every result without rerunning machine-specific work.

## Separate random-level page

An additional [Linux stress-test runner](../benchmarks/README.md) covers every
power of two from 2^10 through 2^20, with a 1 GiB address-space cap per process.
Its [raw results](../benchmarks/random-level-scale/results.json) and
[peak memory](../benchmarks/random-level-scale/memory.json) are kept separately
from the website dataset below. Every completed trial checks structural
invariants and the full key set after insertion; the larger sweep uses one
deterministic trial per size and workload.

The [repeat sweep](../benchmarks/random-level-scale-recheck/results.json)
reruns those sizes after making the insertion-depth cap explicit, then adds
2^21 (2,097,152 keys) for every workload. It uses seed 2026, one trial per group,
a 360-second subprocess deadline, and the same 1 GiB address-space limit.
The [memory record](../benchmarks/random-level-scale-recheck/memory.json)
includes final invariant validation in its peak resident memory measurement.
Its website graphs are at `/random-level-scale.html`; regenerate them using
`benchmark_report --random-level-scale` as shown in the runner instructions.

`/random-level.html` adds a focused benchmark without replacing `results.html`,
`summary.html`, or their original measurements. Links from the visualizer and
both existing report pages lead to it. The new data and SVG downloads live in
`site/dist/random-level-results/` and are included in the GitHub Pages build.

The page preserves the original 140 trials at 1,000, 2,000, 4,000 and 8,000 keys
and adds 140 trials at 16,000, 32,000, 64,000 and 128,000 keys. Both batches
use all seven input families, five trial seeds, seed 2026 and a ten-second
subprocess deadline. Reproduce the two batches in fresh directories:

```sh
PYTHONPATH=src python3 -m balance_trees.benchmark \
  --sizes 1000 2000 4000 8000 --trials 5 --seed 2026 --timeout 10 \
  --strategies random-level --output benchmarks/results/my-random-level-run
PYTHONPATH=src python3 -m balance_trees.benchmark \
  --sizes 16000 32000 64000 128000 --trials 5 --seed 2026 --timeout 10 \
  --strategies random-level --output benchmarks/results/my-random-level-large
PYTHONPATH=src python3 -m balance_trees.benchmark_merge \
  --input benchmarks/results/my-random-level-run benchmarks/results/my-random-level-large \
  --output benchmarks/results/my-random-level-combined
PYTHONPATH=src python3 -m balance_trees.benchmark_report \
  --input benchmarks/results/my-random-level-combined \
  --output src/balance_trees/showcase/site/dist --random-level
```

`benchmark_merge` keeps every recorded trial unchanged and recalculates group
summaries. It requires disjoint sizes and matching machine, Python version,
seed, trial count and measurement settings. It writes a fresh directory and
retains the source batch metadata in `config.json` and `results.json`. To extend
an existing dataset, use its directory as the first merge input and benchmark
only sizes it does not contain.

All generated graphs show a muted dashed `log₂(n)` curve behind the measurements.
This uses the same axes and the actual value of `log₂(n)` without fitting a
multiplier. For time, rotations, bits and scans it is only a numeric guide;
it does not have the metric's units and is not a timing prediction or a complexity
bound. Axis ranges include the guide even when measured costs are zero.

The report command without `--random-level` still regenerates the original
comparison pages and leaves the dedicated page and its measurements intact.

## Review of `random-level`

The original policy and its measurements are preserved. The separate
[`random-level-v2` policy](random-level-v2.md) addresses growing leaf-promotion
costs using local repairs and has an expected-rotation bound. Select the version
explicitly when benchmarking; the existing `/random-level.html` page contains
the original version's measurements.
The separate `/random-level-v2.html` page presents the new policy, expected
rotation bound, paired reports for all seven workloads and downloadable data.

The review fixed two algorithm defects and a missing browser implementation:

- Target depth now uses the **previous** count/priority extrema. Updating the
  interval first made both the strict new-minimum and new-maximum rules
  unreachable. New minima now reach the root; new maxima stay at the inserted
  leaf's depth. The new value enters the summary afterward.
- A promotion reduces the inserted node's depth by one. The implementation uses
  the already measured initial depth to determine the number of promotions,
  avoiding a fresh parent walk after every rotation.
- The policy gets a fresh factory instance per tree/trial, preserving its
  count/extrema state without cross-run contamination. Duplicates consume no
  bits or state. Each unique insertion consumes exactly 64 logical fair bits.
- Both browser engines use one shared generator policy and BigInt arithmetic
  for the 64-bit interval, with integer band rounding matching Python. The
  browser PRNG differs from Python, so equal seeds do not promise equal shapes.

Its persistent state is a count and two extrema outside the nodes. It remains
a heuristic; mapping a priority interval to levels does not enforce a treap
heap or establish logarithmic expected depth. The existing exact recount,
window-budget and hash-heap tests remain in place for the other new strategies.
