"""Find the worst seed-averaged behavior of one strategy at one size."""

import argparse
import csv
import json
import math
from dataclasses import asdict
from pathlib import Path
from statistics import fmean

from .measurement import run_trial
from .sequences import insertion_order
from .strategies import create_strategy


def average_run(
    *,
    strategy: str,
    order: str,
    size: int,
    run: int,
    seed: int,
    seeds_per_run: int,
) -> dict:
    """Run one repetition using several seeds and average its metrics."""
    records = []
    for seed_index in range(seeds_per_run):
        values = insertion_order(order, size, seed + seed_index)
        result = run_trial(values, create_strategy(strategy), seed + seed_index)
        metrics = asdict(result.metrics)
        metrics["seconds"] = result.elapsed_seconds
        metrics["microseconds_per_insertion"] = (
            result.elapsed_seconds * 1e6 / size
        )
        records.append(metrics)
    averaged = {
        key: fmean(record[key] for record in records)
        for key in records[0]
    }
    return {
        "run": run + 1,
        "seeds_per_run": seeds_per_run,
        **averaged,
    }


def worst_case(
    *,
    strategy: str,
    order: str,
    size: int,
    runs: int,
    seed: int,
    seeds_per_run: int | None,
) -> tuple[list[dict], dict]:
    if size < 2:
        raise ValueError("size must be at least 2")
    if runs < 1:
        raise ValueError("runs must be positive")
    if seeds_per_run is None:
        seeds_per_run = max(1, math.ceil(math.log2(size)))
    if seeds_per_run < 1:
        raise ValueError("seeds-per-run must be positive")
    run_averages = [
        average_run(
            strategy=strategy,
            order=order,
            size=size,
            run=run,
            seed=seed + run * seeds_per_run,
            seeds_per_run=seeds_per_run,
        )
        for run in range(runs)
    ]
    metric_keys = [
        key
        for key in run_averages[0]
        if key not in {"run", "seeds_per_run"}
    ]
    worst = {
        "strategy": strategy,
        "order": order,
        "size": size,
        "runs": runs,
        "seeds_per_run": seeds_per_run,
        "total_trials": runs * seeds_per_run,
    }
    for key in metric_keys:
        worst_run = max(run_averages, key=lambda row: row[key])
        worst[f"worst_{key}"] = worst_run[key]
        worst[f"worst_{key}_run"] = worst_run["run"]
    return run_averages, worst


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", default="random-level-v2-1")
    parser.add_argument("--order", default="random")
    parser.add_argument("--size", type=int, default=100000)
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--seeds-per-run", type=int)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--output", type=Path, default=Path("benchmarks/worst-case")
    )
    args = parser.parse_args()
    run_averages, worst = worst_case(
        strategy=args.strategy,
        order=args.order,
        size=args.size,
        runs=args.runs,
        seed=args.seed,
        seeds_per_run=args.seeds_per_run,
    )
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "run_averages.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, run_averages[0].keys())
        writer.writeheader()
        writer.writerows(run_averages)
    (args.output / "worst_case.json").write_text(
        json.dumps(worst, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(worst, indent=2))


if __name__ == "__main__":
    main()
