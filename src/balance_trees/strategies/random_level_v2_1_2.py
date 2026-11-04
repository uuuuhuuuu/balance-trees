"""Random-level v2.1.2: local repairs over the full priority range."""

from dataclasses import dataclass

from .base import RebalanceContext
from .paper import ZigZag
from .random_level_v2 import RandomLevelV2

_LOCAL_REPAIR = ZigZag()


@dataclass(slots=True)
class RandomLevelV212(RandomLevelV2):
    """Use v2.1's growing width with no special minimum or maximum behavior.

    For a b-bit roll, priorities range from 0 through 2**b - 1. This policy
    does not store observed minima or maxima. It uses the full range
    [0, 2**b - 1] as the synthetic interval.

    Consequently, priority 0 is handled by the normal lowest band rather than
    promoting directly to the root, and priority 2**b - 1 is handled by the
    normal highest band rather than remaining at its insertion depth. Every
    priority receives the same band-based target-depth computation.
    """

    def roll_priority(self, context: RebalanceContext) -> int:
        """Sample one priority using a growing logarithmic bit width."""
        bits = max(1, (self.inserted_count + 1).bit_length())
        value = 0
        for _ in range(bits):
            value = (value << 1) | context.bits.bit()
        return value

    def rebalance(self, context: RebalanceContext) -> None:
        priority = self.roll_priority(context)
        bits = max(1, (self.inserted_count + 1).bit_length())

        lowest = 0
        highest = (1 << bits) - 1
        depth = context.stats.insertion_depth

        target = self.target_depth(
            priority, lowest, highest, self.inserted_count, depth
        )
        self.inserted_count += 1
        context.stats.priority = priority

        node = context.inserted
        if depth <= target:
            return
        if depth == target + 1:
            context.promote(node, distance=0)
            return

        # Same local repair as v2: walk to the repair site, then repair either
        # a straight path or a bend.
        distance = depth - target - 2
        for _ in range(distance):
            context.visit(node)
            node = node.parent
        context.visit(node)
        _LOCAL_REPAIR.apply(context, node, distance)
