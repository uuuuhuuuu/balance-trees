"""Depth-weighted leaf promotions with v2 priority tracking."""

import math
from dataclasses import dataclass

from .base import RebalanceContext
from .random_level import TreapPriority

_C = 2.0
_EPSILON = 1.0
_SCALE = 1 << 53


@dataclass(slots=True)
class RandomLevelV3(TreapPriority):
    """Promote strict records to the root; otherwise sample a final depth.

    For non-record insertions at depth d >= 2, stay with probability 1/10
    and promote with probability 9/10, independently of the saved maximum.
    Conditional on promotion, target k in 1..d-1 has weight
    (d / (2 * ln(n)**(1+epsilon)))**(d-k), with n previous inserts.
    Record minima always reach the root. At depth one, non-record
    insertions stay because no target exists. Priority extrema and count
    are still tracked. Target sampling uses scaled floating-point weights
    and 53-bit coins; the promotion gate uses the exact fraction 9/10.
    """

    def rebalance(self, context: RebalanceContext) -> None:
        priority = self.roll_priority(context)
        depth = context.stats.insertion_depth
        count = self.inserted_count
        lowest = self.lowest_priority
        highest = self.highest_priority
        is_record = lowest is not None and priority < lowest

        self.inserted_count += 1
        self.lowest_priority = priority if lowest is None else min(lowest, priority)
        self.highest_priority = priority if highest is None else max(highest, priority)
        context.stats.priority = priority
        node = context.inserted

        if depth == 0:
            return
        if is_record:
            for _ in range(depth):
                context.promote(node, distance=0)
            return
        if depth < 2 or count < 2:
            return

        if not context.choose(node, 9, 10, purpose="promote-leaf"):
            return

        log_ratio = (
            math.log(depth) - math.log(_C)
            - (1.0 + _EPSILON) * math.log(math.log(count))
        )
        # Subtract the largest log weight before exponentiation.
        peak = (depth - 1) if log_ratio >= 0 else 1
        weights = [
            math.exp((depth - level - peak) * log_ratio)
            for level in range(1, depth)
        ]
        suffix = [0.0] * (len(weights) + 1)
        for index in range(len(weights) - 1, -1, -1):
            suffix[index] = math.fsum((weights[index], suffix[index + 1]))

        target = depth - 1
        for index, weight in enumerate(weights[:-1]):
            numerator = min(_SCALE, max(0, round(weight / suffix[index] * _SCALE)))
            if context.choose(
                node, numerator, _SCALE, purpose="choose-final-level"
            ):
                target = index + 1
                break

        for _ in range(depth - target):
            context.promote(node, distance=0)
