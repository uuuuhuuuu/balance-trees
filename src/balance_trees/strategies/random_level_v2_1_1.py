"""Random-level v2.1.1: local repairs with fixed synthetic priority bounds."""

from dataclasses import dataclass

from .base import RebalanceContext
from .paper import ZigZag
from .random_level_v2 import RandomLevelV2

_LOCAL_REPAIR = ZigZag()


@dataclass(slots=True)
class RandomLevelV211(RandomLevelV2):
    """Use v2.1's growing width, but fixed second-smallest/second-largest bounds.

    For a b-bit roll, priorities range from 0 through 2**b - 1. This policy
    does not store observed minima or maxima. It behaves as though the observed
    interval were always [1, 2**b - 2]:

    * priority 0 is below the synthetic minimum and promotes to the root;
    * priority 2**b - 1 is above the synthetic maximum and stays at its
      insertion depth;
    * every other priority is mapped through v2's band-based target selection.

    The minimum width is two bits so that the synthetic interval is nonempty.
    """

    def roll_priority(self, context: RebalanceContext) -> int:
        """Sample one priority using a growing logarithmic bit width."""
        bits = max(2, (self.inserted_count + 1).bit_length())
        value = 0
        for _ in range(bits):
            value = (value << 1) | context.bits.bit()
        return value

    def rebalance(self, context: RebalanceContext) -> None:
        priority = self.roll_priority(context)
        bits = max(2, (self.inserted_count + 1).bit_length())

        lowest = 1
        highest = (1 << bits) - 2
        depth = context.stats.insertion_depth

        target = self.target_depth(
            priority, lowest, highest, self.inserted_count, depth
        )
        self.inserted_count += 1
        context.stats.priority = priority

        node = context.inserted
        if priority < lowest:
            for _ in range(depth):
                context.promote(node, distance=0)
            return

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
