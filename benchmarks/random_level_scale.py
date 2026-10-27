"""Run a memory-capped powers-of-two sweep of the random-level strategy (Linux)."""

import argparse
import json
import resource
import sys
from pathlib import Path

from balance_trees.benchmark import run_benchmarks
from balance_trees.sequences import ORDERS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-power", type=int, default=10)
    parser.add_argument("--max-power", type=int, default=21)
    parser.add_argument("--memory-mib", type=int, default=1024)
    parser.add_argument("--timeout", type=float, default=360)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        parser.error("This runner uses Linux address-space limits and RSS units.")
    if not 1 <= args.min_power <= args.max_power <= 30:
        parser.error("Require 1 <= min-power <= max-power <= 30.")
    if args.memory_mib < 64:
        parser.error("Use at least 64 MiB for the interpreter and validation.")

    previous = resource.getrlimit(resource.RLIMIT_AS)
    limits = [args.memory_mib * 1024**2]
    limits.extend(limit for limit in previous if limit != resource.RLIM_INFINITY)
    cap = min(limits)
    # Children inherit this limit, including input generation and final validation.
    # Run one subprocess at a time; no large trees accumulate across trials.
    resource.setrlimit(resource.RLIMIT_AS, (cap, previous[1]))
    try:
        results = run_benchmarks(
            args.output,
            sizes=[1 << power for power in range(args.min_power, args.max_power + 1)],
            trials=args.trials,
            seed=args.seed,
            strategies=["random-level"],
            orders=list(ORDERS),
            timeout=args.timeout,
        )
    finally:
        resource.setrlimit(resource.RLIMIT_AS, previous)

    memory = {
        "address_space_limit_bytes": cap,
        "peak_child_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        * 1024,
        "note": "Peak resident memory of the largest isolated trial, including validation; address-space cap also includes virtual mappings. Linux ru_maxrss is in KiB.",
    }
    (args.output / "memory.json").write_text(json.dumps(memory, indent=2) + "\n")
    print(json.dumps(memory, indent=2))
    if any(row["status"] != "complete" for row in results["trials"]):
        raise SystemExit("Some trials did not complete; inspect trials.jsonl.")


if __name__ == "__main__":
    main()
