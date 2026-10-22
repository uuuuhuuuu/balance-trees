"""CSV exports and readable reports; no tree or strategy logic belongs here."""

import csv
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .measurement import TrialResult
from .metrics import TrialMetrics
from .statistics import TrialAggregate

GROUP_FIELDS = ("strategy", "order", "n")
SUMMARY_FIELDS = (
    *GROUP_FIELDS,
    "trials",
    "mean_depth",
    "mean_depth_se",
    "mean_depth_over_log2_n",
    "mean_height",
    "worst_key_mean_depth",
    "worst_key_mean_depth_over_log2_n",
    "mean_insertion_depth",
    "mean_rotations",
    "mean_rotations_se",
    "max_rotations",
    "mean_visits",
    "mean_visits_se",
    "max_visits",
    "mean_random_bits",
    "mean_random_bits_se",
    "max_random_bits",
    "rotations_within_2_edges_fraction",
)


def text_table(headers: list[str], rows: list[list[str]]) -> str:
    """A dependency-free, aligned table without truncation or terminal colors."""
    widths = [
        max([len(header), *(len(row[i]) for row in rows)])
        for i, header in enumerate(headers)
    ]

    def line(cells: list[str]) -> str:
        return "  ".join(cell.rjust(width) for cell, width in zip(cells, widths))

    return "\n".join(
        [
            line(headers),
            "  ".join("-" * width for width in widths),
            *(line(row) for row in rows),
        ]
    )


def render_summary(summaries: list[dict], *, seed: int, trials: int) -> str:
    lines = [
        "BINARY SEARCH TREE EXPERIMENT",
        f"Seed: {seed} | Trials per group: {trials} | Root depth: 0",
        "Halving: p(k) = 2^(-k-1); continue upward after success AND failure.",
        "Constant-half: p = 1/2 at every decision; continue to root.",
        "Inverse-depth: p = 1/h throughout insertion; h is initial leaf depth.",
        "Depth +/- SE is the mean of trial-average depths and its standard error.",
        "Worst-key is max_key(mean_trial(depth)); height is mean_trial(max_depth).",
        "Work columns are per insertion, including the initial root insertion.",
        "MaxRot is an observed maximum, not a theoretical worst-case bound.",
        "",
    ]
    orders = dict.fromkeys(row["order"] for row in summaries)
    for order in orders:
        rows = []
        for row in summaries:
            if row["order"] != order:
                continue
            error = row["mean_depth_se"]
            depth = (
                f"{row['mean_depth']:.2f} +/- {error:.2f}"
                if error is not None
                else f"{row['mean_depth']:.2f} (SE n/a)"
            )
            rows.append(
                [
                    str(row["n"]),
                    row["strategy"],
                    depth,
                    f"{row['worst_key_mean_depth']:.2f}",
                    f"{row['mean_height']:.2f}",
                    f"{row['mean_rotations']:.3f}",
                    f"{row['mean_visits']:.2f}",
                    f"{row['mean_random_bits']:.2f}",
                    str(row["max_rotations"]),
                ]
            )
        lines.extend(
            [
                f"Insertion order: {order}",
                text_table(
                    [
                        "n",
                        "Flavor",
                        "Depth +/- SE",
                        "Worst-key",
                        "Height",
                        "Rot/ins",
                        "Visits/ins",
                        "Bits/ins",
                        "MaxRot",
                    ],
                    rows,
                ),
                "",
            ]
        )
    lines.extend(
        [
            "Interpretation:",
            "- Compare depth/log2(n) across sizes; finite samples do not prove O(log n).",
            "- Random order is fixed per size: SE reflects rebalancing randomness only.",
            "- Halving has expected <1 rotation per insertion, but walks to the root.",
            "- Inverse-depth has expected <=1 rotation; it uses the initial insertion depth.",
            "- Constant-half can perform expected Theta(insertion depth) rotations.",
            "- Full-walk visits and these independent coin trials cost Theta(insertion depth).",
            "- Bits are logical fair bits consumed, not physical PRNG words.",
        ]
    )
    return "\n".join(lines) + "\n"


@dataclass(slots=True)
class ResultWriter:
    trials: csv.DictWriter
    summaries: csv.DictWriter
    nodes: csv.DictWriter
    distances: csv.DictWriter

    def add_trial(
        self,
        group: dict,
        trial: int,
        order_seed: int,
        rotation_seed: int,
        result: TrialResult,
    ) -> None:
        self.trials.writerow(
            {
                **group,
                "trial": trial,
                "order_seed": order_seed,
                "rotation_seed": rotation_seed,
                **asdict(result.metrics),
            }
        )

    def add_group(self, group: dict, aggregate: TrialAggregate) -> dict:
        summary = {**group, **aggregate.summary()}
        self.summaries.writerow(summary)
        self.nodes.writerows({**group, **row} for row in aggregate.node_rows())
        self.distances.writerows({**group, **row} for row in aggregate.distance_rows())
        return summary


@contextmanager
def result_files(output: Path) -> Iterator[ResultWriter]:
    with ExitStack() as stack:

        def writer(filename: str, columns: tuple[str, ...]) -> csv.DictWriter:
            handle = stack.enter_context(
                (output / filename).open("w", newline="", encoding="utf-8")
            )
            result = csv.DictWriter(handle, columns)
            result.writeheader()
            return result

        yield ResultWriter(
            trials=writer(
                "trials.csv",
                (
                    *GROUP_FIELDS,
                    "trial",
                    "order_seed",
                    "rotation_seed",
                    *(field.name for field in fields(TrialMetrics)),
                ),
            ),
            summaries=writer("summary.csv", SUMMARY_FIELDS),
            nodes=writer(
                "node_depths.csv",
                (*GROUP_FIELDS, "key", "trials", "mean_depth", "depth_se"),
            ),
            distances=writer(
                "rotation_distances.csv",
                (
                    *GROUP_FIELDS,
                    "distance",
                    "rotations",
                    "fraction",
                    "cumulative_fraction",
                ),
            ),
        )


def save_report(output: Path, summaries: list[dict], *, seed: int, trials: int) -> str:
    report = render_summary(summaries, seed=seed, trials=trials)
    (output / "report.txt").write_text(report, encoding="utf-8")
    markdown = (
        "# BST rotation strategy comparison\n\n"
        "Reference: [Brodal, Bottom-up Rebalancing Binary Search Trees by Flipping a Coin]"
        "(https://arxiv.org/abs/2404.08287).\n\n"
        "`paper-zig` uses continuation probability 1/2; `paper-zigzag` uses 3/4. "
        "The experimental full upward walks continue after either coin outcome.\n\n"
        "```text\n" + report + "```\n\n"
        "See `config.json` for seeds and definitions, `trials.csv` for independent runs, "
        "`summary.csv` for aggregates, `node_depths.csv` for per-key uncertainty, "
        "and `rotation_distances.csv` for rotation locality. "
        "Blank standard errors indicate fewer than two trials.\n"
    )
    (output / "report.md").write_text(markdown, encoding="utf-8")
    return report
