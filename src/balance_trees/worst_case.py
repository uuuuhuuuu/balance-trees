"""Find worst seed-averaged behavior across a linear size sweep."""

import argparse
import csv
import html
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


def linear_sizes(min_size: int, max_size: int, count: int) -> list[int]:
    if min_size < 2 or max_size < min_size or count < 2:
        raise ValueError(
            "Use min-size >= 2, max-size >= min-size, and size-count >= 2."
        )
    raw = [
        min_size + (max_size - min_size) * index / (count - 1)
        for index in range(count)
    ]
    sizes = sorted({max(2, round(value)) for value in raw})
    if len(sizes) < count:
        sizes = list(range(min_size, max_size + 1))
        step = max(1, (len(sizes) - 1) // (count - 1))
        sizes = sizes[::step]
        if sizes[-1] != max_size:
            sizes[-1] = max_size
    return sizes


def svg_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def rotations_svg(rows: list[dict], *, strategy: str, order: str) -> str:
    """Plot the worst seed-averaged rotations per key at each size."""
    width, height = 900, 520
    left, top, plot_width, plot_height = 82, 58, 740, 360
    sizes = [row["size"] for row in rows]
    values = [row["worst_rotations"] for row in rows]
    ymax = max(values) * 1.12

    def x(size: int) -> float:
        return left + (size - sizes[0]) / (sizes[-1] - sizes[0]) * plot_width

    def y(value: float) -> float:
        return top + plot_height * (1 - max(0, value) / ymax)

    points = " ".join(
        f"{'M' if index == 0 else 'L'}{x(row['size']):.2f},{y(row['worst_rotations']):.2f}"
        for index, row in enumerate(rows)
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{svg_escape(strategy)} · worst seed-averaged rotations per key</title>',
        f'<desc id="desc">Worst rotations per insertion over seed-averaged runs for {svg_escape(order)} inputs.</desc>',
        '<style>text{font:12px system-ui,sans-serif;fill:#334155}.grid{stroke:#e2e8f0}path,line{vector-effect:non-scaling-stroke}</style>',
        f'<rect width="{width}" height="{height}" rx="14" fill="white"/>',
        f'<text x="26" y="32" style="font-size:17px;font-weight:650">{svg_escape(strategy)} · worst seed-averaged rotations/key</text>',
        f'<text x="26" y="52" style="fill:#64748b">{svg_escape(order)} inputs · worst of seed-averaged runs at each size</text>',
    ]
    for tick in range(6):
        value = ymax * tick / 5
        yy = y(value)
        parts += [
            f'<line class="grid" x1="{left}" x2="{left + plot_width}" y1="{yy:.2f}" y2="{yy:.2f}"/>',
            f'<text x="{left - 10}" y="{yy + 4:.2f}" text-anchor="end">{value:.3g}</text>',
        ]
    for row in rows:
        xx = x(row["size"])
        parts += [
            f'<line class="grid" x1="{xx:.2f}" x2="{xx:.2f}" y1="{top}" y2="{top + plot_height}"/>',
            f'<text x="{xx:.2f}" y="{top + plot_height + 22}" text-anchor="middle">{row["size"]:,}</text>',
        ]
    parts.append(
        f'<path d="{points}" stroke="#dc2626" stroke-width="3" fill="none"/>'
    )
    for row in rows:
        parts.append(
            f'<circle cx="{x(row["size"]):.2f}" cy="{y(row["worst_rotations"]):.2f}" r="5" fill="#dc2626"><title>n={row["size"]:,}; worst average rotations/key={row["worst_rotations"]:.6g}; worst run={row["worst_rotations_run"]}</title></circle>'
        )
    parts += [
        f'<text x="26" y="{top + plot_height + 48}" style="fill:#64748b;font-size:11px">x: keys · y: rotations per insertion · red: worst seed-averaged rotations/key</text>',
        "</svg>",
    ]
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", default="random-level-v2-1")
    parser.add_argument("--order", default="random")
    parser.add_argument("--min-size", type=int, default=1000)
    parser.add_argument("--max-size", type=int, default=100000)
    parser.add_argument("--size-count", type=int, default=10)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seeds-per-run", type=int)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--output", type=Path, default=Path("benchmarks/worst-case-sweep")
    )
    args = parser.parse_args()
    sizes = linear_sizes(args.min_size, args.max_size, args.size_count)
    args.output.mkdir(parents=True, exist_ok=False)
    sweep = []
    all_run_averages = []
    for index, size in enumerate(sizes):
        print(
            f"Starting size {index + 1}/{len(sizes)}: n={size:,}",
            flush=True,
        )
        run_averages, worst = worst_case(
            strategy=args.strategy,
            order=args.order,
            size=size,
            runs=args.runs,
            seed=args.seed + index * 10000,
            seeds_per_run=args.seeds_per_run,
        )
        all_run_averages.extend(run_averages)
        sweep.append(worst)
        print(
            f"Finished n={size:,}: worst average rotations/key={worst['worst_rotations']:.3g}",
            flush=True,
        )
    fields = list(sweep[0].keys())
    with (args.output / "worst_case_sweep.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(sweep)
    with (args.output / "all_run_averages.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, all_run_averages[0].keys())
        writer.writeheader()
        writer.writerows(all_run_averages)
    (args.output / "rotations.svg").write_text(
        rotations_svg(sweep, strategy=args.strategy, order=args.order),
        encoding="utf-8",
    )
    metadata = {
        "strategy": args.strategy,
        "order": args.order,
        "min_size": args.min_size,
        "max_size": args.max_size,
        "size_count": args.size_count,
        "sizes": sizes,
        "runs": args.runs,
        "seeds_per_run": args.seeds_per_run,
        "seed": args.seed,
        "total_trials": sum(row["total_trials"] for row in sweep),
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Sweep ready in {args.output}")


if __name__ == "__main__":
    main()
