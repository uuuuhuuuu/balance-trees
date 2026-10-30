"""Trace one random-order v2 tree and plot insertion depth for every key."""

import argparse
import csv
import html
import json
import math
from pathlib import Path

from .flavors import TreeFlavor
from .sequences import insertion_order
from .strategies import create_strategy


def rolling_mean(values: list[int], window: int) -> list[float]:
    """Trailing arithmetic mean; the first point uses the available prefix."""
    result = []
    total = 0
    for index, value in enumerate(values):
        total += value
        if index >= window:
            total -= values[index - window]
        result.append(total / min(index + 1, window))
    return result


def svg_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def build_svg(
    depths: list[int],
    rolling: list[float],
    samples: list[dict],
    *,
    strategy: str,
    order: str,
    seed: int,
    window: int,
) -> str:
    """Draw per-insertion depth, its rolling mean, sampled height, and log2 n."""
    width, height = 1100, 560
    left, top, plot_width, plot_height = 78, 52, 950, 400
    n = len(depths)
    ymax = max(
        1,
        max(depths),
        max(sample["height"] for sample in samples),
        max(1, n).bit_length() - 1,
    ) * 1.08

    def x(index: int) -> float:
        return left + index / max(1, n - 1) * plot_width

    def y(value: float) -> float:
        return top + plot_height * (1 - max(0, value) / ymax)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{svg_escape(strategy)} · insertion depth during one {svg_escape(order)} run</title>',
        f'<desc id="desc">Depth d of each inserted key, a {window}-insertion rolling mean, sampled tree height, and a green log2(n) reference. Seed {seed}; {n:,} unique keys.</desc>',
        '<style>text{font:12px system-ui,sans-serif;fill:#334155}.grid{stroke:#e2e8f0}path,line{vector-effect:non-scaling-stroke}</style>',
        f'<rect width="{width}" height="{height}" rx="14" fill="white"/>',
        f'<text x="26" y="30" style="font-size:17px;font-weight:650">{svg_escape(strategy)} · one {svg_escape(order)} sequence</text>',
        f'<text x="26" y="50" style="fill:#64748b">{n:,} insertions · seed {seed} · d = depth at insertion</text>',
    ]
    for tick in range(6):
        value = ymax * tick / 5
        yy = y(value)
        parts += [
            f'<line class="grid" x1="{left}" x2="{left + plot_width}" y1="{yy:.2f}" y2="{yy:.2f}"/>',
            f'<text x="{left - 10}" y="{yy + 4:.2f}" text-anchor="end">{value:.3g}</text>',
        ]
    for tick in range(6):
        index = round(tick * (n - 1) / 5)
        xx = x(index)
        parts += [
            f'<line class="grid" x1="{xx:.2f}" x2="{xx:.2f}" y1="{top}" y2="{top + plot_height}"/>',
            f'<text x="{xx:.2f}" y="{top + plot_height + 22}" text-anchor="middle">{index + 1:,}</text>',
        ]
    depth_points = " ".join(
        f"{'M' if index == 0 else 'L'}{x(index):.2f},{y(value):.2f}"
        for index, value in enumerate(depths)
    )
    rolling_points = " ".join(
        f"{'M' if index == 0 else 'L'}{x(index):.2f},{y(value):.2f}"
        for index, value in enumerate(rolling)
    )
    height_points = " ".join(
        f"{'M' if index == 0 else 'L'}{x(sample['insertion'] - 1):.2f},{y(sample['height']):.2f}"
        for index, sample in enumerate(samples)
    )
    log_points = " ".join(
        f"{'M' if index == 0 else 'L'}{x(index):.2f},{y(math.log2(index + 1)):.2f}"
        for index in range(n)
    )
    parts += [
        f'<path d="{log_points}" stroke="#059669" stroke-width="2.5" stroke-dasharray="7 5" fill="none" opacity="0.9"/>',
        f'<path d="{height_points}" stroke="#dc2626" stroke-width="2.5" fill="none" opacity="0.85"/>',
        f'<path d="{depth_points}" stroke="#94a3b8" stroke-width="1" fill="none" opacity="0.45"/>',
        f'<path d="{rolling_points}" stroke="#2563eb" stroke-width="2.5" fill="none"/>',
        f'<text x="{left + plot_width - 8}" y="{y(math.log2(n)) - 10:.2f}" text-anchor="end" style="fill:#059669;font-size:11px">log₂ n reference</text>',
        f'<text x="{left + plot_width - 8}" y="{y(samples[-1]["height"]) - 10:.2f}" text-anchor="end" style="fill:#dc2626;font-size:11px">sampled height</text>',
        f'<text x="{left + plot_width - 8}" y="{y(rolling[-1]) + 18:.2f}" text-anchor="end" style="fill:#2563eb;font-size:11px">rolling mean d</text>',
        f'<text x="26" y="{top + plot_height + 48}" style="fill:#64748b;font-size:11px">x: insertion number · y: depth · gray: individual d · blue: {window}-insertion rolling mean · red: sampled tree height · green dashed: log₂ n</text>',
        "</svg>",
    ]
    return "\n".join(parts)


def trace_insertions(
    *,
    strategy: str,
    order: str,
    size: int,
    seed: int,
    window: int,
    sample_count: int,
) -> tuple[list[dict], list[dict]]:
    if size < 1:
        raise ValueError("size must be positive")
    if window < 1:
        raise ValueError("window must be positive")
    if sample_count < 2:
        raise ValueError("sample-count must be at least 2")
    values = insertion_order(order, size, seed)
    flavor = TreeFlavor(create_strategy(strategy), seed=seed)
    records = []
    samples = []
    sample_every = max(1, size // (sample_count - 1))
    for index, key in enumerate(values):
        stats = flavor.insert(key)
        if not stats.inserted:
            raise ValueError("insertion sequence must contain unique keys")
        depth = stats.insertion_depth
        records.append(
            {
                "insertion": index + 1,
                "key": key,
                "depth": depth,
                "rotations": stats.rotations,
                "visits": stats.visits,
                "random_bits": stats.random_bits,
            }
        )
        if index % sample_every == 0 or index == size - 1:
            depths = flavor.tree.depths()
            samples.append(
                {
                    "insertion": index + 1,
                    "height": max(depths.values()),
                    "mean_depth": sum(depths.values()) / len(depths),
                }
            )
    return records, samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", default="random-level-v2")
    parser.add_argument("--order", default="random")
    parser.add_argument("--size", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--window", type=int, default=100)
    parser.add_argument("--sample-count", type=int, default=101)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/v2-insertion-depth"))
    args = parser.parse_args()
    records, samples = trace_insertions(
        strategy=args.strategy,
        order=args.order,
        size=args.size,
        seed=args.seed,
        window=args.window,
        sample_count=args.sample_count,
    )
    args.output.mkdir(parents=True, exist_ok=False)
    depths = [record["depth"] for record in records]
    rolling = rolling_mean(depths, args.window)
    with (args.output / "insertion_depth.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            [
                "insertion",
                "key",
                "depth",
                "rolling_mean_depth",
                "rotations",
                "visits",
                "random_bits",
            ],
        )
        writer.writeheader()
        for record, mean in zip(records, rolling):
            writer.writerow({**record, "rolling_mean_depth": mean})
    with (args.output / "tree_evolution.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle, ["insertion", "height", "mean_depth"]
        )
        writer.writeheader()
        writer.writerows(samples)
    svg = build_svg(
        depths,
        rolling,
        samples,
        strategy=args.strategy,
        order=args.order,
        seed=args.seed,
        window=args.window,
    )
    (args.output / "insertion_depth.svg").write_text(svg, encoding="utf-8")
    metadata = {
        "strategy": args.strategy,
        "order": args.order,
        "size": args.size,
        "seed": args.seed,
        "window": args.window,
        "sample_count": args.sample_count,
        "records": len(records),
        "samples": len(samples),
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Trace ready in {args.output}")


if __name__ == "__main__":
    main()
