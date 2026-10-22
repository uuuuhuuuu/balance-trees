"""Aggregate independent trials, keeping per-key expectations distinct."""

import math
from collections import Counter
from collections.abc import Iterator
from statistics import fmean, stdev

from .measurement import TrialResult
from .metrics import TrialMetrics


def standard_error(values: list[float]) -> float | None:
    """Missing with one trial; a single observation cannot estimate uncertainty."""
    return stdev(values) / math.sqrt(len(values)) if len(values) > 1 else None


class TrialAggregate:
    """Incremental per-key moments plus small, per-trial metric records."""

    def __init__(self, n: int):
        if n < 2:
            raise ValueError("trial aggregates require at least two keys")
        self.n = n
        self.records: list[TrialMetrics] = []
        self.depth_totals = [0] * (n + 1)
        self.depth_squares = [0] * (n + 1)
        self.distances: Counter[int] = Counter()

    def add(self, result: TrialResult) -> None:
        if set(result.depths) != set(range(1, self.n + 1)):
            raise ValueError("aggregate expects exactly the keys 1 through n")
        self.records.append(result.metrics)
        self.distances.update(result.rotation_distances)
        for key, depth in result.depths.items():
            self.depth_totals[key] += depth
            self.depth_squares[key] += depth * depth

    def node_rows(self) -> Iterator[dict]:
        trials = len(self.records)
        if trials == 0:
            raise ValueError("cannot summarize zero trials")
        for key in range(1, self.n + 1):
            total = self.depth_totals[key]
            squares = self.depth_squares[key]
            # Exact integer subtraction avoids loss of precision in the variance.
            error = (
                math.sqrt(
                    (trials * squares - total * total) / (trials**2 * (trials - 1))
                )
                if trials > 1
                else None
            )
            yield {
                "key": key,
                "trials": trials,
                "mean_depth": total / trials,
                "depth_se": error,
            }

    def distance_rows(self) -> Iterator[dict]:
        total = sum(self.distances.values())
        cumulative = 0
        for distance, count in sorted(self.distances.items()):
            cumulative += count
            yield {
                "distance": distance,
                "rotations": count,
                "fraction": count / total,
                "cumulative_fraction": cumulative / total,
            }

    def summary(self) -> dict:
        if not self.records:
            raise ValueError("cannot summarize zero trials")
        summary = {"trials": len(self.records)}
        for field in (
            "mean_depth",
            "mean_insertion_depth",
            "mean_rotations",
            "mean_visits",
            "mean_random_bits",
            "mean_scanned_nodes",
        ):
            values = [getattr(record, field) for record in self.records]
            summary[field] = fmean(values)
            if field != "mean_insertion_depth":
                summary[field + "_se"] = standard_error(values)
        summary["mean_height"] = fmean(record.height for record in self.records)
        summary["mean_depth_over_log2_n"] = summary["mean_depth"] / math.log2(self.n)
        summary["worst_key_mean_depth"] = max(self.depth_totals[1:]) / len(self.records)
        summary["worst_key_mean_depth_over_log2_n"] = summary[
            "worst_key_mean_depth"
        ] / math.log2(self.n)
        for field in (
            "max_rotations",
            "max_visits",
            "max_random_bits",
            "max_scanned_nodes",
        ):
            summary[field] = max(getattr(record, field) for record in self.records)
        total = sum(self.distances.values())
        summary["rotations_within_2_edges_fraction"] = (
            sum(count for distance, count in self.distances.items() if distance <= 2)
            / total
            if total
            else None
        )
        return summary
