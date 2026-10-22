"""Run and validate one trial, independently of reporting or CLI choices."""

from collections import Counter
from dataclasses import dataclass
from statistics import fmean

from .flavors import TreeFlavor
from .metrics import TrialMetrics
from .strategies.base import Strategy


@dataclass(slots=True)
class TrialResult:
    metrics: TrialMetrics
    depths: dict[int, int]
    rotation_distances: Counter[int]


def run_trial(
    values: list[int],
    strategy: Strategy,
    seed: int,
    *,
    check_every_insertion: bool = False,
) -> TrialResult:
    if not values:
        raise ValueError("an experimental trial needs at least one key")
    flavor = TreeFlavor(strategy, seed=seed)
    rotations = visits = random_bits = insertion_depth = 0
    max_rotations = max_visits = max_random_bits = 0
    scanned_nodes = max_scanned_nodes = 0
    distances: Counter[int] = Counter()
    for key in values:
        stats = flavor.insert(key)
        if not stats.inserted:
            raise ValueError("experimental insertion orders must contain unique keys")
        insertion_depth += stats.insertion_depth
        rotations += stats.rotations
        visits += stats.visits
        random_bits += stats.random_bits
        scanned_nodes += stats.scanned_nodes
        max_scanned_nodes = max(max_scanned_nodes, stats.scanned_nodes)
        max_rotations = max(max_rotations, stats.rotations)
        max_visits = max(max_visits, stats.visits)
        max_random_bits = max(max_random_bits, stats.random_bits)
        distances.update(stats.rotation_distances)
        if check_every_insertion:
            flavor.tree.depths()
    depths = flavor.tree.depths()
    if set(depths) != set(values):
        raise AssertionError("insertion lost or introduced keys")
    n = len(values)
    return TrialResult(
        TrialMetrics(
            mean_depth=fmean(depths.values()),
            height=max(depths.values()),
            mean_insertion_depth=insertion_depth / n,
            mean_rotations=rotations / n,
            max_rotations=max_rotations,
            mean_visits=visits / n,
            max_visits=max_visits,
            mean_random_bits=random_bits / n,
            max_random_bits=max_random_bits,
            mean_scanned_nodes=scanned_nodes / n,
            max_scanned_nodes=max_scanned_nodes,
        ),
        depths,
        distances,
    )
