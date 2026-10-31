"""Compare v2.1 mean pre-balance insertion depth with log2(n) and 2 log2(n)."""

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


def measure_size(
    *,
    strategy: str,
    size: int,
    trials: int,
    seed: int,
) -> dict:
    """Measure mean initial insertion depth over independent random trials."""
    values = []
    for trial in range(trials):
        sequence = insertion_order("random", size, seed + trial)
        result = run_trial(sequence, create_strategy(strategy), seed + trial)
        metrics = asdict(result.metrics)
        values.append(metrics["mean_insertion_depth"])
    mean_depth = fmean(values)
    return {
        "size": size,
        "trials": trials,
        "mean_insertion_depth": mean_depth,
        "log2_n": math.log2(size),
        "two_log2_n": 2 * math.log2(size),
        "ratio_to_log2_n": mean_depth / math.log2(size),
        "ratio_to_two_log2_n": mean_depth / (2 * math.log2(size)),
    }


def svg_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def build_svg(rows: list[dict], *, strategy: str) -> str:
    """Plot measured mean insertion depth with log2(n) and 2 log2(n)."""
    width, height = 940, 540
    left, top, plot_width, plot_height = 82, 58, 760, 380
    sizes = [row["size"] for row in rows]
    ymax = max(
        max(row["mean_insertion_depth"] for row in rows),
        max(row["two_log2_n"] for row in rows),
    ) * 1.12

    def x(size: int) -> float:
        return left + (size - sizes[0]) / (sizes[-1] - sizes[0]) * plot_width

    def y(value: float) -> float:
        return top + plot_height * (1 - max(0, value) / ymax)

    measured = " ".join(
        f"{'M' if index == 0 else 'L'}{x(row['size']):.2f},{y(row['mean_insertion_depth']):.2f}"
        for index, row in enumerate(rows)
    )
    log_reference = " ".join(
        f"{'M' if index == 0 else 'L'}{x(row['size']):.2f},{y(row['log2_n']):.2f}"
        for index, row in enumerate(rows)
    )
    two_log_reference = " ".join(
        f"{'M' if index == 0 else 'L'}{x(row['size']):.2f},{y(row['two_log2_n']):.2f}"
        for index, row in enumerate(rows)
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{svg_escape(strategy)} · mean initial insertion depth</title>',
        f'<desc id="desc">Mean depth at which each new node is initially inserted before balancing, for random inputs. Blue: measurement; green dashed: log2(n); orange dashed: 2 log2(n).</desc>',
        '<style>text{font:12px system-ui,sans-serif;fill:#334155}.grid{stroke:#e2e8f0}path,line{vector-effect:non-scaling-stroke}</style>',
        f'<rect width="{width}" height="{height}" rx="14" fill="white"/>',
        f'<text x="26" y="32" style="font-size:17px;font-weight:650">{svg_escape(strategy)} · mean initial insertion depth</text>',
        f'<text x="26" y="52" style="fill:#64748b">Random inputs · depth before balancing · averaged over trials</text>',
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
    parts += [
        f'<path d="{two_log_reference}" stroke="#d97706" stroke-width="2.5" stroke-dasharray="7 5" fill="none" opacity="0.9"/>',
        f'<path d="{log_reference}" stroke="#059669" stroke-width="2.5" stroke-dasharray="7 5" fill="none" opacity="0.9"/>',
        f'<path d="{measured}" stroke="#2563eb" stroke-width="3" fill="none"/>',
    ]
    for row in rows:
        parts.append(
            f'<circle cx="{x(row["size"]):.2f}" cy="{y(row["mean_insertion_depth"]):.2f}" r="5" fill="#2563eb"><title>n={row["size"]:,}; mean insertion depth={row["mean_insertion_depth"]:.6g}; log2(n)={row["log2_n"]:.6g}; 2 log2(n)={row["two_log2_n"]:.6g}; ratio={row["ratio_to_log2_n"]:.6g}</title></circle>'
        )
    parts += [
        f'<text x="{left + plot_width - 8}" y="{y(rows[-1]["two_log2_n"]) - 10:.2f}" text-anchor="end" style="fill:#d97706;font-size:11px">2 log₂ n</text>',
        f'<text x="{left + plot_width - 8}" y="{y(rows[-1]["log2_n"]) - 10:.2f}" text-anchor="end" style="fill:#059669;font-size:11px">log₂ n</text>',
        f'<text x="{left + plot_width - 8}" y="{y(rows[-1]["mean_insertion_depth"]) + 18:.2f}" text-anchor="end" style="fill:#2563eb;font-size:11px">measured mean</text>',
        f'<text x="26" y="{top + plot_height + 48}" style="fill:#64748b;font-size:11px">x: keys · y: mean initial insertion depth · blue: measurement · green dashed: log₂ n · orange dashed: 2 log₂ n</text>',
        "</svg>",
    ]
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", default="random-level-v2-1")
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=[64, 1024, 16384, 262144, 4194304, 67108864, 134217728, 268435456],
    )
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/v2-1-insertion-depth-compare"),
    )
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be positive")
    sizes = sorted(set(args.sizes))
    if any(size < 2 for size in sizes):
        parser.error("all sizes must be at least 2")
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for index, size in enumerate(sizes):
        print(
            f"Starting size {index + 1}/{len(sizes)}: n={size:,}",
            flush=True,
        )
        row = measure_size(
            strategy=args.strategy,
            size=size,
            trials=args.trials,
            seed=args.seed,
        )
        rows.append(row)
        print(
            f"Finished n={size:,}: mean insertion depth={row['mean_insertion_depth']:.3g}; "
            f"log2(n)={row['log2_n']:.3g}; 2 log2(n)={row['two_log2_n']:.3g}",
            flush=True,
        )
    with (args.output / "insertion_depth_compare.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (args.output / "insertion_depth_compare.svg").write_text(
        build_svg(rows, strategy=args.strategy),
        encoding="utf-8",
    )
    metadata = {
        "strategy": args.strategy,
        "order": "random",
        "sizes": sizes,
        "trials": args.trials,
        "seed": args.seed,
        "total_trials": len(sizes) * args.trials,
        "metric": "mean_insertion_depth before balancing",
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Comparison ready in {args.output}")


if __name__ == "__main__":
    main()
