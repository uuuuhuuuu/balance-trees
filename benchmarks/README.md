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

For a larger, memory-capped random-level test on Linux:

```sh
PYTHONPATH=src python3 benchmarks/random_level_scale.py \
  --min-power 10 --max-power 21 --memory-mib 1024 --timeout 360 \
  --output benchmarks/results/my-random-level-scale
```

This tests every power of two from 1,024 through 2,097,152 keys, including
exactly 2^16, across all seven workloads. Each isolated trial validates the final
BST ordering, parent pointers, absence of cycles, and complete key set. The
default is one trial per group with seed 2026 and a 360-second deadline; use
`--trials 5` for repeated measurements or raise `--max-power` to explore further.
The 1 GiB address-space cap applies to input generation, insertion, and validation.
Memory exhaustion is recorded as an error; incomplete trials make the runner
exit unsuccessfully. `memory.json` records the effective cap and largest child
process's peak resident memory, including validation.

The checked-in [powers-of-two sweep](random-level-scale/results.json),
[summary CSV](random-level-scale/summary.csv), and
[memory measurement](random-level-scale/memory.json) preserve this larger test
separately from the existing five-trial website measurements. One trial provides
no standard error and does not establish a balance or complexity guarantee.

The recorded sweep completed all 77 trials in 649 seconds. Peak child resident
memory was 311,812,096 bytes (297.4 MiB), including validation. At 2^20 keys,
final heights ranged from 46 to 94 edges across the seven workloads.

The [repeat sweep](random-level-scale-recheck/results.json) reruns the original
sizes and extends every workload to 2^21 (2,097,152 keys), using the explicit
insertion-depth cap. Regenerate its website graphs with:

```sh
PYTHONPATH=src python3 -m balance_trees.benchmark_report \
  --input benchmarks/random-level-scale-recheck \
  --output src/balance_trees/showcase/site/dist --random-level-scale
```

Open `/random-level-scale.html` on the local showcase server. The dedicated
page and `random-level-scale-results/` downloads preserve the earlier reports.

The repeat sweep completed all 84 trials in 1,277 seconds. Peak child resident
memory was 597,504,000 bytes (569.8 MiB), below the 1 GiB address-space cap.
All 77 repeated trials matched every original non-timing metric exactly;
[validation.json](random-level-scale-recheck/validation.json) records the
comparison and baseline checksum. The seven new 2^21 trials passed final
invariant checks, with heights ranging from 54 to 110 edges.
