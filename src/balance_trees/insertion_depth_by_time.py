"""Measure the expected pre-balancing insertion depth by insertion index.

For v2.1, this script inserts the same number of keys in several independent
random orders.  For each insertion index i, it records the depth at which the
new node first lands, before v2.1 performs any rebalancing.  It then averages
that depth over all runs.

The output answers the question:

    What is E[depth of the leaf created by insertion i]?

It is intentionally different from the average depth of all nodes in the final
tree: later rotations can move an earlier node after it has been inserted.

Usage
-----

    python -m balance_trees.insertion_depth_by_time --size 100000 --runs 20

Outputs
-------

- ``insertion_depth_by_time.csv``: one row per insertion index, with the
  seed-averaged pre-balancing depth and logarithmic reference curves.
- ``insertion_depth_by_time.svg``: a plot of the measured curve against
  ``ln(i)`` and ``2 ln(i)``.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

from .insertion_order import insertion_order
from .tree import TreeFlavor


def measure_insertion_depth_by_time(
    size: int,
    runs: int,
    *,
    seed: int = 12345,
) -> list[float]:
    """Return the average pre-balancing insertion depth for each index.

    The returned list has ``size`` entries.  Entry ``i - 1`` is the average,
    across all runs, of the depth at which the ``i``-th inserted key first
    lands before rebalancing.
    """
    if size <= 0:
        raise ValueError("size must be positive")
    if runs <= 0:
        raise ValueError("runs must be positive")

    totals = [0] * size

    for run in range(runs):
        order = insertion_order(size, seed=seed + run)
        tree = TreeFlavor.V21()

        for index, key in enumerate(order):
            tree.insert(key)
            totals[index] += tree.stats.insertion_depth

    return [total / runs for total in totals]


def write_results(
    mean_depths: list[float],
    csv_path: Path,
    svg_path: Path,
) -> None:
    """Write the per-index results and a logarithmic comparison plot."""
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "insertion_index",
                "mean_insertion_depth",
                "ln_i",
                "two_ln_i",
                "log2_i",
            ]
        )
        for index, depth in enumerate(mean_depths, start=1):
            natural_log = math.log(index)
            writer.writerow(
                [
                    index,
                    f"{depth:.6f}",
                    f"{natural_log:.6f}",
                    f"{2 * natural_log:.6f}",
                    f"{math.log2(index):.6f}",
                ]
            )

    # Plot every point for modest inputs, but cap the number of plotted points
    # for very large inputs so the SVG remains readable and reasonably sized.
    plot_indices = list(range(1, len(mean_depths) + 1))
    if len(plot_indices) > 2000:
        stride = math.ceil(len(plot_indices) / 2000)
        plot_indices = plot_indices[::stride]
        if plot_indices[-1] != len(mean_depths):
            plot_indices.append(len(mean_depths))

    width, height = 900, 560
    left, right = 72, 24
    top, bottom = 28, 58

    max_depth = max(mean_depths)
    max_reference = 2 * math.log(len(mean_depths))
    y_max = max(max_depth, max_reference) * 1.08

    def x_pixel(index: int) -> float:
        return left + (index - 1) / (len(mean_depths) - 1) * (width - left - right)

    def y_pixel(value: float) -> float:
        return height - bottom - value / y_max * (height - top - bottom)

    def polyline(values: list[float]) -> str:
        return " ".join(
            f"{x_pixel(index):.2f},{y_pixel(value):.2f}"
            for index, value in zip(plot_indices, values)
        )

    measured = [mean_depths[index - 1] for index in plot_indices]
    natural = [math.log(index) for index in plot_indices]
    doubled = [2 * math.log(index) for index in plot_indices]

    ticks = []
    for value in range(0, math.ceil(y_max) + 1):
        if value <= y_max:
            y = y_pixel(value)
            ticks.append(
                f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" '
                f'y2="{y:.2f}" stroke="#dddddd" stroke-width="1" />'
            )
            ticks.append(
                f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" '
                f'font-size="12" fill="#444444">{value}</text>'
            )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="white"/>
  <text x="{width / 2:.0f}" y="18" text-anchor="middle" font-size="16" font-weight="bold">v2.1 average pre-balancing insertion depth</text>
  {''.join(ticks)}
  <polyline points="{polyline(doubled)}" fill="none" stroke="#999999" stroke-width="2" stroke-dasharray="6 4"/>
  <polyline points="{polyline(natural)}" fill="none" stroke="#4477aa" stroke-width="2" stroke-dasharray="4 4"/>
  <polyline points="{polyline(measured)}" fill="none" stroke="#cc3311" stroke-width="2.5"/>
  <line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" stroke="black"/>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" stroke="black"/>
  <text x="{(left + width - right) / 2:.0f}" y="{height - 20}" text-anchor="middle" font-size="13">Insertion index i</text>
  <text x="20" y="{(top + height - bottom) / 2:.0f}" text-anchor="middle" font-size="13" transform="rotate(-90 20 {(top + height - bottom) / 2:.0f})">Mean insertion depth</text>
  <text x="{width - right}" y="{y_pixel(2 * math.log(len(mean_depths))) - 8:.2f}" text-anchor="end" font-size="12" fill="#666666">2 ln(i)</text>
  <text x="{width - right}" y="{y_pixel(math.log(len(mean_depths))) - 8:.2f}" text-anchor="end" font-size="12" fill="#4477aa">ln(i)</text>
  <text x="{width - right}" y="{y_pixel(mean_depths[-1]) - 8:.2f}" text-anchor="end" font-size="12" fill="#cc3311">measured</text>
</svg>
"""

    svg_path.write_text(svg, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Measure the average pre-balancing depth of each new leaf in v2.1, "
            "averaged over independent random insertion orders."
        )
    )
    parser.add_argument("--size", type=int, required=True, help="final number of keys")
    parser.add_argument("--runs", type=int, default=20, help="number of random seeds")
    parser.add_argument("--seed", type=int, default=12345, help="base RNG seed")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="directory for the CSV and SVG outputs",
    )
    args = parser.parse_args()

    mean_depths = measure_insertion_depth_by_time(
        args.size,
        args.runs,
        seed=args.seed,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "insertion_depth_by_time.csv"
    svg_path = args.output_dir / "insertion_depth_by_time.svg"
    write_results(mean_depths, csv_path, svg_path)

    print(f"Wrote {csv_path}")
    print(f"Wrote {svg_path}")
    print(f"Final mean pre-balancing insertion depth: {mean_depths[-1]:.4f}")
    print(f"2 ln(n): {2 * math.log(args.size):.4f}")


if __name__ == "__main__":
    main()
