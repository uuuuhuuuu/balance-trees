"""Run real Python implementations in isolated, time-bounded local trials."""

import argparse
import csv
import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from time import perf_counter

from .experiment import derived_seed
from .measurement import run_trial
from .sequences import ORDERS, insertion_order
from .statistics import standard_error
from .strategies import STRATEGIES, create_strategy, strategy_factory


def worker(request: dict) -> dict:
    values = insertion_order(request["order"], request["n"], request["order_seed"])
    # Warm interpreter paths on a separate, fresh policy. No measured tree reuse.
    run_trial(values[: min(32, len(values))], create_strategy(request["strategy"]), 0)
    result = run_trial(values, create_strategy(request["strategy"]), request["seed"])
    return {
        **asdict(result.metrics),
        "seconds": result.elapsed_seconds,
        "microseconds_per_insertion": result.elapsed_seconds * 1e6 / len(values),
    }


def summarize(records: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for row in records:
        groups.setdefault((row["strategy"], row["order"], row["n"]), []).append(row)
    summaries = []
    for (strategy, order, n), rows in groups.items():
        complete = [row for row in rows if row["status"] == "complete"]
        summary = {
            "strategy": strategy,
            "order": order,
            "n": n,
            "completed_trials": len(complete),
            "requested_trials": len(rows),
            "status": "complete"
            if len(complete) == len(rows)
            else rows[len(complete)]["status"],
        }
        if complete:
            for key in complete[0]["metrics"]:
                values = [row["metrics"][key] for row in complete]
                summary[key] = max(values) if key.startswith("max_") else fmean(values)
                if not key.startswith("max_"):
                    summary[key + "_se"] = standard_error(values)
        summaries.append(summary)
    return summaries


def write_csv(path: Path, rows: list[dict]) -> None:
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run_benchmarks(
    output: Path,
    *,
    sizes: list[int],
    trials: int,
    seed: int,
    strategies: list[str],
    orders: list[str],
    timeout: float,
) -> dict:
    if (
        not sizes
        or any(type(n) is not int or n < 2 for n in sizes)
        or trials < 1
        or not 0 < timeout < float("inf")
        or not strategies
        or any(s not in STRATEGIES for s in strategies)
        or not orders
        or any(o not in ORDERS for o in orders)
        or any(len(set(v)) != len(v) for v in (sizes, strategies, orders))
    ):
        raise ValueError(
            "Use unique sizes >=2, known strategies/orders, positive trials and a finite timeout."
        )
    output.mkdir(parents=True, exist_ok=False)
    cpu = platform.processor() or platform.machine()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        cpu = next(
            (
                line.split(":", 1)[1].strip()
                for line in cpuinfo.read_text().splitlines()
                if line.startswith("model name")
            ),
            cpu,
        )
    metadata = {
        "schema_version": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "cpu": cpu,
        "logical_cpus": os.cpu_count(),
        "sizes": sizes,
        "trials": trials,
        "seed": seed,
        "strategies": strategies,
        "orders": orders,
        "timeout_seconds": timeout,
        "execution": "Sequential isolated subprocesses on this computer; no parallel timed trials.",
        "timing": "perf_counter around the instrumented insertion loop, including cost counters; excludes input generation, warmup, process startup, final invariant validation and rendering.",
        "deadline": "End-to-end deadline per subprocess, including warmup and validation. A timeout is censored, not a runtime or a completed tree. Remaining trials in that group are not run.",
        "sampling": "One fixed permutation per size shared across strategies/trials; paired rotation seeds derived with SHA-256. SE is across trial seeds, conditional on that input.",
        "limits": "Python instrumentation timings, not bare algorithm timings. No general complexity or balance guarantee follows from these finite samples. No timing comparison is made against the optimized browser preview.",
        "catalog": strategy_factory.catalog(),
    }
    (output / "config.json").write_text(json.dumps(metadata, indent=2) + "\n")
    records = []
    started = perf_counter()
    for n in sizes:
        for order in orders:
            for strategy in strategies:
                stopped = False
                for trial in range(trials):
                    request = {
                        "strategy": strategy,
                        "order": order,
                        "n": n,
                        "trial": trial,
                        "order_seed": derived_seed(seed, "order", n),
                        "seed": derived_seed(seed, "rotation", n, order, trial),
                    }
                    row = {**request, "status": "not_run", "metrics": {}}
                    if not stopped:
                        try:
                            process = subprocess.run(
                                [
                                    sys.executable,
                                    "-m",
                                    "balance_trees.benchmark",
                                    "--worker",
                                ],
                                input=json.dumps(request),
                                capture_output=True,
                                text=True,
                                timeout=timeout,
                                check=True,
                            )
                            row.update(
                                status="complete", metrics=json.loads(process.stdout)
                            )
                        except subprocess.TimeoutExpired:
                            row.update(
                                status="timeout",
                                detail=f"Subprocess exceeded {timeout:g} s deadline",
                            )
                            stopped = True
                        except subprocess.CalledProcessError as error:
                            row.update(status="error", detail=error.stderr[-4000:])
                            stopped = True
                    records.append(row)
                    # A crash or interruption still leaves every finished trial reviewable.
                    with (output / "trials.jsonl").open(
                        "a", encoding="utf-8"
                    ) as handle:
                        handle.write(json.dumps(row) + "\n")
            print(
                f"Completed n={n:,}, order={order} ({perf_counter() - started:.1f} s)",
                flush=True,
            )
    metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
    metadata["wall_seconds"] = perf_counter() - started
    results = {"metadata": metadata, "summaries": summarize(records), "trials": records}
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    (output / "config.json").write_text(json.dumps(metadata, indent=2) + "\n")
    write_csv(output / "summary.csv", results["summaries"])
    write_csv(
        output / "trials.csv",
        [
            {**{k: v for k, v in row.items() if k != "metrics"}, **row["metrics"]}
            for row in records
        ],
    )
    return results


def main() -> None:
    if sys.argv[1:] == ["--worker"]:
        print(json.dumps(worker(json.load(sys.stdin))))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("benchmarks/results/local-large")
    )
    parser.add_argument(
        "--sizes", type=int, nargs="+", default=[1000, 4000, 16000, 64000]
    )
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--timeout", type=float, default=3)
    parser.add_argument(
        "--strategies", nargs="+", choices=STRATEGIES, default=list(STRATEGIES)
    )
    parser.add_argument("--orders", nargs="+", choices=ORDERS, default=list(ORDERS))
    args = parser.parse_args()
    try:
        run_benchmarks(
            args.output,
            sizes=args.sizes,
            trials=args.trials,
            seed=args.seed,
            strategies=args.strategies,
            orders=args.orders,
            timeout=args.timeout,
        )
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"All results: {args.output / 'results.json'}")


if __name__ == "__main__":
    main()
