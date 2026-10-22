# Experimental balance trees

A Python research playground for binary search trees that store **only keys and
structural pointers**. The first experiment tests a full upward walk with
rotation probabilities `1/2, 1/4, 1/8, ...` after each leaf insertion.

Inspired by [Gerth Stølting Brodal, *Bottom-up Rebalancing Binary Search Trees by
Flipping a Coin*](https://arxiv.org/abs/2404.08287). The paper's two stopping rules
are included as baselines; the halving walk is a separate experimental strategy.

## Interactive showcase

Rotation Lab is a separate visual guide with treaps and all six experimental
BST flavors. It shows search comparisons, leaf insertion, coin decisions, and
the state before and after every primitive rotation. Play, pause, step backward,
jump to the next rotation or insertion, pan, zoom, and switch to presentation mode.

```sh
PYTHONPATH=src python -m balance_trees.showcase --port 8000
```

Open `http://127.0.0.1:8000`. Choose increasing, random, converging, decreasing,
pairs, bitonic, or runs. Paste comma-separated integers or import a `.csv` / `.txt`
file. Signed integers and duplicates are supported; the showcase caps inputs
at 64 keys so individual steps remain inspectable.

The local server visualizes the actual Python implementations. The same static
website can be hosted from `src/balance_trees/showcase/site/dist/`; it uses a
browser reference simulator when the Python API is absent. Their random
generators differ, and the interface identifies which engine produced the run.
Export and import JSON traces to replay an exact Python run on any static host.

See [the showcase guide and trace format](docs/showcase.md) for hosting,
extension points, and exporting another implementation.

### Public hosting on GitHub

GitHub Pages deployment is configured in [.github/workflows/pages.yml](.github/workflows/pages.yml).
In [the repository's Pages settings](https://github.com/vaclavkouril/balance-trees/settings/pages),
select **GitHub Actions** as the source, then run **Publish Rotation Lab** from
the Actions tab. Later source pushes to the default branch publish automatically
after the tests pass. No custom secrets or server are required.

After deployment, the public URL is **https://vaclavkouril.github.io/balance-trees/**.
See [the GitHub Pages setup guide](docs/github-pages.md) for the one-time steps,
local preview, and troubleshooting.

## Run it

Python 3.11+; the implementation, reports, and tests require no third-party
packages. Run these commands from the repository root:

```sh
# Print a tree and an aligned table of insertion costs.
PYTHONPATH=src python -m balance_trees.demo --keys 4 2 6 1 3 5 7 --seed 42

# Inspect the tree after every insertion; --ascii supports plain terminals.
PYTHONPATH=src python -m balance_trees.demo --trace --ascii

# Export the final tree as DOT and render a scalable diagram.
PYTHONPATH=src python -m balance_trees.demo \
  --keys 8 4 12 2 6 10 14 --seed 2026 \
  --dot benchmarks/results/trees/halving.dot \
  --graph benchmarks/results/trees/halving.svg --highlight-key 14

# Compare six flavors on all seven insertion-order families.
PYTHONPATH=src python -m balance_trees.experiment \
  --sizes 64 256 1024 --trials 25 --seed 2026 \
  --output benchmarks/results/my-run --progress

# Focus on the proposed strategy and validate every intermediate tree.
PYTHONPATH=src python -m balance_trees.experiment \
  --sizes 32 128 --trials 10 --strategies halving none \
  --orders increasing converging pairs --check-every-insertion \
  --output benchmarks/results/checked-run

# Run the test suite.
PYTHONPATH=src python -m unittest discover -s tests -v
```

Each experiment requires a **new output directory** to preserve earlier results.
A final invariant check runs after every trial; checking after each insertion is
optional because it adds substantial analysis work.

For installed commands and optional formatting tools:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/balance-tree-demo --trace
.venv/bin/balance-tree-experiment --help
.venv/bin/ruff format src tests
.venv/bin/ruff check src tests
```

## Architecture and adding flavors

```text
src/balance_trees/
  tree.py             Plain BST, leaf insertion, lookup, invariant validation
  rotations.py        Left/right rotations and node promotion
  flavors.py          Compose a base tree, strategy, and random-bit source
  strategies/
    base.py           Strategy protocol and instrumented rebalance context
    halving.py        Continue-to-root experiment
    fixed.py          Constant probability and inverse initial-depth walks
    walk.py           Shared full upward traversal and rotation accounting
    paper.py          Geometric stopping policy and Zig / ZigZag rules
    __init__.py       CLI flavor registry (factories, not shared instances)
  random_bits.py      Exact rational coins; counted logical fair bits
  metrics.py          Insertion and trial measurements outside the tree
  sequences.py        Seven reproducible insertion-order families
  measurement.py      Run and validate one trial
  statistics.py       Trial aggregation and per-key depth estimates
  rendering.py        Bounded Unicode / ASCII tree diagrams
  graphviz.py         Deterministic DOT export and SVG / PNG / PDF rendering
  reporting.py        Aligned text, Markdown, and CSV exports
  experiment.py       Experiment orchestration and CLI
  demo.py             Interactive inspection through a command-line trace
```

`tests/` contains standard-library `unittest` tests. Generated experiment data
lives under `benchmarks/results/` and is ignored by Git. No strategy-specific
state is stored in `Node` or `BST`; random sources and instrumentation are external.
Only insertion and lookup are currently supported; deletion is outside this experiment.

Use the base tree directly, or compose a flavor:

```python
from fractions import Fraction
from balance_trees import (
    BST, ConstantWalk, GeometricStop, HalvingWalk, InverseDepthWalk, TreeFlavor, ZigZag,
)

plain = BST()
plain.insert(10)

candidate = TreeFlavor(HalvingWalk(), seed=42)
for key in [4, 2, 6, 1, 3, 5, 7]:
    stats = candidate.insert(key)
    print(key, stats.rotations, stats.visits, stats.random_bits)
print(candidate)

# Reuse the stopping policy with a different rotation rule or probability.
paper_variant = TreeFlavor(GeometricStop(Fraction(3, 4), ZigZag()), seed=42)

constant_half = TreeFlavor(ConstantWalk(), seed=42)
inverse_depth = TreeFlavor(InverseDepthWalk(), seed=42)
```

Add a strategy by implementing `rebalance(context)` and registering a factory
in `strategies/__init__.py`. Use `context.promote(node, distance)` to apply and
count rotations. Use `context.choose(node, numerator, denominator)` to count
and sample a decision while making its cursor available to visual tracing.
Neither the insertion pipeline nor the base tree needs to change. Duplicate keys
are ignored without rebalancing or consuming random bits.

## Graphviz visualization

`--dot path.dot` exports the final tree without additional dependencies.
`--graph path.svg` renders it using the system `dot` executable; `.png` and
`.pdf` are also supported. Install the Graphviz system package if `dot` is not
on `PATH`; no Python `graphviz` package is required. Rendering follows the
[Graphviz command-line interface](https://graphviz.org/doc/info/command.html).

Edges are labelled **L** and **R**, with invisible placeholders preserving the
left/right position of single children. Use `--show-nulls` to draw missing
children explicitly, or `--highlight-key 14` to emphasize an element. Graphviz
exports the complete tree; the text printer's depth and node limits do not
truncate the graph. DOT node IDs are deterministic, and visualization leaves
the tree and random-bit stream unchanged.

The same support is available independently of the CLI:

```python
from balance_trees import HalvingWalk, TreeFlavor, render_graphviz, to_dot, write_dot

flavor = TreeFlavor(HalvingWalk(), seed=2026)
for key in [8, 4, 12, 2, 6, 10, 14]:
    flavor.insert(key)

source = to_dot(flavor.tree, title="Halving experiment")
write_dot(flavor.tree, "tree.dot")
render_graphviz(flavor.tree, "tree.svg", highlight_key=14, show_nulls=True)
```

Call these functions after individual insertions to capture rotation sequences.
Graphviz rendering is optional and separate from benchmark measurements.

## Exact halving semantics

1. Insert a leaf using ordinary BST search, then set the cursor to that leaf.
2. At decision `k`, starting at zero, promote the cursor over its parent with
   probability `2^(-k-1)`.
3. After either outcome, move to the cursor's **current parent**. A successful
   rotation therefore skips the demoted old parent.
4. Increment `k`; stop when the cursor reaches the root.

Thus `k` counts decisions, not levels on the original search path. Rotation
locality is recorded separately as the original path distance of the promoted
node from the inserted leaf. The schedule consults neither insertion depth nor
`n`; the inserted leaf's depth is measured only for analysis.

The paper baselines are `paper-zig` (Algorithm 1, continuation probability `1/2`)
and `paper-zigzag` (Algorithm 2, continuation probability `3/4`). The straight
case of the latter promotes the parent **once**; it is not standard double
zig-zig splaying. `none` performs plain BST insertion.

## Statistical output

Available CLI flavors:

| Flavor | Rotation probability and stopping rule |
| --- | --- |
| `halving` | `1/2, 1/4, 1/8, ...`; continue to the root |
| `constant-half` | `1/2` at every decision; continue to the root |
| `inverse-depth` | `1/h` at every decision; continue to the root |
| `none` | Plain BST insertion |
| `paper-zig` | Continue with probability `1/2`; otherwise rotate once and stop |
| `paper-zigzag` | Continue with probability `3/4`; otherwise apply the paper rule and stop |

All three full walks share the same traversal: after a successful promotion,
move to the promoted node's new parent; after failure, move to its existing
parent. Only their probability schedules differ.

For `inverse-depth`, `h` means the inserted vertex's **initial depth**, the
number of edges from the root before rebalancing. A new leaf's subtree height
is zero, so literal subtree height cannot be the denominator. The depth is
collected during ordinary insertion search, frozen for that insertion, and
never stored in a node. Root insertion skips rebalancing; depth one rotates
with certainty and consumes no random bits.

`inverse-depth` has expected at most one rotation per insertion, since at most
`h` decisions each have probability `1/h`. It deliberately relaxes the paper's
local-information requirement by using the insertion depth. `constant-half`
can use expected `Theta(h)` rotations. Both still traverse to the root and
neither has the halving strategy's geometric bias toward nearby decisions.

On strictly increasing or decreasing inputs, `inverse-depth` deterministically
produces a chain: every new extreme is inserted at depth one, its rotation
probability is one, and it becomes the root. The final mean depth is exactly
`(n - 1)/2`. This is an outcome of the requested rule, covered by a regression
test, rather than evidence of a balancing guarantee.

The completed six-flavor comparison uses sizes 64, 256, and 1,024, with 25 trials
per workload and seed 2026 (3,150 trials total). See the generated
[comparison report](benchmarks/results/all-six-strategies/report.md) and
[summary CSV](benchmarks/results/all-six-strategies/summary.csv).

The console and saved reports show mean final depth **+/- standard error**,
worst per-key mean depth, mean height, and rotation / ancestor-visit / random-bit
costs per insertion. They also show the largest rotation count observed in one
insertion. Root depth is zero; all per-insertion means include the first insertion.

Each run produces:

| File | Contents |
| --- | --- |
| `config.json` | Parameters, Python version, seed derivation, and metric definitions |
| `trials.csv` | One row per independently seeded run, including work maxima |
| `summary.csv` | Trial means and standard errors; depth / `log2(n)` ratios |
| `node_depths.csv` | Final depth mean and standard error for **each key** |
| `rotation_distances.csv` | Rotation-distance counts, fractions, and cumulative fractions |
| `report.txt`, `report.md` | Human-readable comparison tables and interpretation notes |

The seven workloads are random, increasing, decreasing, converging, pairs,
bitonic, and runs. One random permutation per size is held fixed across trials
and flavors, so uncertainty measures rebalancing randomness conditional on that
sequence. It does not estimate variability across all random input orders.
Strategies share the same seed per trial, but differing random-bit consumption
means they do not necessarily use corresponding random events.

`worst_key_mean_depth` means `max_key(mean_trial(depth))`. This differs from
`mean_height = mean_trial(max_key(depth))`; only the first directly examines the
goal of low expected depth for every key. Selecting the worst key from finite
samples does not provide a simultaneous confidence bound. Standard errors use
independent **trial-level** observations, rather than treating correlated nodes
or insertions as independent samples. One-trial errors are blank, not zero.

Random-bit counts measure logical fair bits requested from a seeded Python
PRNG, not its internal word consumption. Coins compare binary expansions
lazily, avoiding float underflow for very small probabilities. Runtime timings
are deliberately excluded: work counts distinguish rebalancing from the initial
search, instrumentation, printing, and final validation.

## Which research goals does this meet?

For a fixed pre-insertion tree, let `h` be the inserted leaf's initial depth,
`R` the number of rotations, and `V` the number of rebalancing decision sites.

- **No balance metadata:** each node stores `key`, `left`, `right`, `parent`.
- **Expected constant rotations:** `E[R | tree] < sum(k >= 0, 2^(-k-1)) = 1`
  for finite trees. This is a bound per insertion, even for an unfavorable tree;
  it is not a constant bound on the expected maximum over many insertions.
- **Local rotations:** later decisions have geometrically smaller rotation
  probabilities. Their original path distances grow by at most two per decision.
- **Local inputs:** the strategy uses the insertion cursor, tree pointers,
  fresh random bits, and a temporary decision counter.
- **Rebalancing time:** `h - R <= V <= h`, so `E[V] >= h - 1`.
  The full upward walk does **not** achieve expected constant rebalancing time.
- **Random bits:** independently sampling every visited decision costs between
  one and two logical bits in expectation per decision, hence expected
  `Theta(h)` bits for this implementation. Constant rotations do not imply
  constant random bits.
- **Expected node depths:** an experimental question; finite-size comparisons
  cannot establish an asymptotic logarithmic guarantee.

Worst-case rotations can grow as `ceil(h/2)`. Tests cover the all-success case,
continued walking after failure, exact coin probabilities, and ordering / parent
links after every insertion for all permutations of six keys across all flavors.
