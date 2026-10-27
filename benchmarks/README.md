# Benchmarks

Run `PYTHONPATH=src python3 -m balance_trees.benchmark --help` from the repository
root. Raw run directories under `results/` are ignored to protect source history
from local experiments. Each run requires a new directory.

The completed machine measurements, all statuses, CSV/JSON downloads and SVG
graphs shipped with the website are in
`src/balance_trees/showcase/site/dist/results/`.

See [methodology and reproduction](../docs/benchmarks.md). Correctness tests are
separate in `tests/`; a small subprocess test checks the benchmark/report pipeline.

`random-level-v2/` retains the separate policy's 63-trial validation, group
summaries and comparisons against paired trials from the original dataset.
See [the policy, bound and reproduction instructions](../docs/random-level-v2.md).
