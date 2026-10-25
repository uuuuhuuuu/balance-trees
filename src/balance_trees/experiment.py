"""CLI orchestration for reproducible strategy comparisons."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

from .measurement import run_trial
from .reporting import result_files, save_report
from .sequences import ORDERS, insertion_order
from .statistics import TrialAggregate
from .strategies import STRATEGIES, create_strategy


def derived_seed(master: int, *parts: object) -> int:
    encoded = json.dumps([master, *parts], separators=(",", ":")).encode()
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")


def run_experiment(
    output: Path,
    sizes: list[int],
    trials: int,
    seed: int,
    strategies: list[str],
    orders: list[str],
    *,
    check_every_insertion: bool = False,
    progress: bool = False,
) -> str:
    if trials < 1 or not sizes or any(n < 2 for n in sizes):
        raise ValueError("use at least one trial and sizes >= 2")
    if not strategies or any(name not in STRATEGIES for name in strategies):
        raise ValueError("select at least one known strategy")
    if not orders or any(name not in ORDERS for name in orders):
        raise ValueError("select at least one known insertion order")
    if any(len(set(items)) != len(items) for items in (sizes, strategies, orders)):
        raise ValueError("sizes, strategies and orders must not contain duplicates")
    # Require a fresh destination to protect earlier experiment results.
    output.mkdir(parents=True, exist_ok=False)
    metadata = {
        "seed": seed,
        "sizes": sizes,
        "trials": trials,
        "strategies": strategies,
        "orders": orders,
        "python_version": platform.python_version(),
        "check_every_insertion": check_every_insertion,
        "paper": "https://arxiv.org/abs/2404.08287",
        "halving_probability": "2**(-k-1), k counts decisions starting at zero",
        "full_walks": {
            "halving": "p(k)=2**(-k-1), k starts at zero",
            "constant-half": "p=1/2 at every decision",
            "inverse-depth": "p=1/h, h is initial insertion depth, frozen for the whole walk; root skips rebalancing",
        },
        "ascent": "after rotation, continue at the promoted node's new parent",
        "random_order": "one fixed permutation per n, shared across trials and strategies",
        "random_bits": "logical fair bits requested, not physical PRNG word consumption",
        "seeds": "first 8 bytes of SHA-256 of compact JSON [master, *parts]",
        "uncertainty": "sample standard error across independent rotation seeds",
        "depth_unit": "edges; root depth zero",
        "rotation_distance": "original search-path edges from inserted leaf to promoted node",
        "baselines": {
            "paper-zig": {"continue_probability": "1/2"},
            "paper-zigzag": {"continue_probability": "3/4"},
        },
        "priority_free": {
            "recount-root": "bottom-up exact 1/s root lottery; transient full-tree recount",
            "window-root": "same rule with 64 actual node inspections per insertion",
            "hash-priority": "SplitMix64(key XOR seed), recomputed; key breaks ties; heuristic",
        },
        "scanned_nodes": "actual recount inspections, excluding initial BST search and coin/priority decisions; no cached subtree sizes in Python",
        "hash_seed": "external trial rotation_seed; fixed 64-bit mixer seed, not fresh random bits per insertion",
    }
    (output / "config.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    summaries = []
    with result_files(output) as writer:
        for n in sizes:
            order_seed = derived_seed(seed, "order", n)
            for order in orders:
                values = insertion_order(order, n, order_seed)
                for strategy in strategies:
                    aggregate = TrialAggregate(n)
                    group = {"strategy": strategy, "order": order, "n": n}
                    for trial in range(trials):
                        rotation_seed = derived_seed(seed, "rotation", n, order, trial)
                        result = run_trial(
                            values,
                            create_strategy(strategy),
                            rotation_seed,
                            check_every_insertion=check_every_insertion,
                        )
                        writer.add_trial(
                            group, trial, order_seed, rotation_seed, result
                        )
                        aggregate.add(result)
                    summaries.append(writer.add_group(group, aggregate))
                if progress:
                    print(
                        f"Completed n={n}, order={order}, trials={trials}", flush=True
                    )
    return save_report(output, summaries, seed=seed, trials=trials)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[64, 256, 1024])
    parser.add_argument("--trials", type=int, default=25)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--strategies", nargs="+", choices=STRATEGIES, default=list(STRATEGIES)
    )
    parser.add_argument("--orders", nargs="+", choices=ORDERS, default=list(ORDERS))
    parser.add_argument(
        "--output", type=Path, default=Path("benchmarks/results/halving")
    )
    parser.add_argument("--check-every-insertion", action="store_true")
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args()
    try:
        report = run_experiment(
            args.output,
            args.sizes,
            args.trials,
            args.seed,
            args.strategies,
            args.orders,
            check_every_insertion=args.check_every_insertion,
            progress=args.progress,
        )
    except (ValueError, FileExistsError) as error:
        parser.error(str(error))
    print(report, end="")
    print(f"Results written to {args.output}")


if __name__ == "__main__":
    main()
