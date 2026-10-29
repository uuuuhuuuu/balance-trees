"""Sample final depths, including the root, with a fixed promotion gate."""

import math
from dataclasses import dataclass

from .base import RebalanceContext
from .random_level import TreapPriority

_C = 2.0
_EPSILON = 1.0
_SCALE = 1 << 53


@dataclass(slots=True)
class RandomLevelV3(TreapPriority):
    """Stay with probability 1/10 on every non-root insertion.

    Otherwise sample final depth k in 0..d-1 with weights
    (d / (2 * ln(n)**(1+epsilon)))**(d-k), then perform d-k rotations.
    No special record-minimum rule applies. Count and priority extrema
    remain tracked. At depth one, promotion necessarily reaches the root;
    no logarithm is needed. The initial root cannot rotate.
    Target sampling uses scaled float weights and 53-bit conditional coins.
    """

    def rebalance(self, context: RebalanceContext) -> None:
        priority = self.roll_priority(context)
        depth = context.stats.insertion_depth
        count = self.inserted_count
        lowest, highest = self.lowest_priority, self.highest_priority
        self.inserted_count += 1
        self.lowest_priority = priority if lowest is None else min(lowest, priority)
        self.highest_priority = priority if highest is None else max(highest, priority)
        context.stats.priority = priority
        node = context.inserted

        if depth == 0:
            return
        if not context.choose(node, 9, 10, purpose="promote-leaf"):
            return

        target = 0
        if depth > 1:
            log_ratio = (
                math.log(depth) - math.log(_C)
                - (1.0 + _EPSILON) * math.log(math.log(count))
            )
            peak = depth if log_ratio >= 0 else 1
            weights = [
                math.exp((depth - level - peak) * log_ratio)
                for level in range(depth)
            ]
            suffix = [0.0] * (depth + 1)
            for index in range(depth - 1, -1, -1):
                suffix[index] = math.fsum((weights[index], suffix[index + 1]))
            target = depth - 1
            for index, weight in enumerate(weights[:-1]):
                numerator = min(_SCALE, max(0, round(weight / suffix[index] * _SCALE)))
                if context.choose(
                    node, numerator, _SCALE, purpose="choose-final-level"
                ):
                    target = index
                    break

        for _ in range(depth - target):
            context.promote(node, distance=0)
