"""A third random-level policy: sample a final level, then promote v1-style."""

import math
from dataclasses import dataclass

from .base import RebalanceContext
from .random_level import TreapPriority

_C = 2.0
_EPSILON = 1e-9
_SCALE = 1 << 53


@dataclass(slots=True)
class RandomLevelV3(TreapPriority):
    """Sample the inserted leaf's final level from a depth-aware distribution.

    Keeps v2's priority rolls and observed-extrema tracking. The no-rotation
    outcome has weight 1 minus the normalized saved maximum priority. A final
    level k in 1..d-1 has weight (d / (2 log^(1+epsilon) n))^(d-k). After
    sampling, the leaf is promoted from insertion depth d to level k.
    """

    def rebalance(self, context: RebalanceContext) -> None:
        priority = self.roll_priority(context)
        depth = context.stats.insertion_depth
        previous_count = self.inserted_count

        lowest = self.lowest_priority
        highest = self.highest_priority
        self.inserted_count += 1
        self.lowest_priority = (
            priority if lowest is None else min(lowest, priority)
        )
        self.highest_priority = (
            priority if highest is None else max(highest, priority)
        )
        context.stats.priority = priority

        if depth == 0 or previous_count == 0:
            return

        saved_max = self.highest_priority / (1 << 64)
        no_rotation_weight = max(0.0, 1.0 - saved_max)
        denominator = _C * max(math.log(previous_count), 1.0) ** (
            1.0 + _EPSILON
        )
        level_weight = depth / denominator

        candidates = [(depth, no_rotation_weight)]
        candidates.extend(
            (level, level_weight ** (depth - level))
            for level in range(1, depth)
        )

        remaining = sum(weight for _, weight in candidates)
        target = depth

        for level, weight in candidates:
            if remaining <= 0.0:
                break
            numerator = min(_SCALE, round(weight / remaining * _SCALE))
            if context.choose(
                context.inserted, numerator, _SCALE, purpose="choose-final-level"
            ):
                target = level
                break
            remaining -= weight

        node = context.inserted
        for _ in range(depth - target):
            context.promote(node, distance=0)
