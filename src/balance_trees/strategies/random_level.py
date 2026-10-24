"""Treap-like random priorities with interval-based target-depth balancing."""

from dataclasses import dataclass

from .base import RebalanceContext

PRIORITY_BITS = 64


@dataclass
class TreapPriority:
    """Roll a priority per insertion, then rotate it to a target depth.

    Priorities are not stored on nodes. The strategy retains only the number
    of inserted nodes and the lowest/highest priorities observed so far.
    """

    inserted_count: int = 0
    lowest_priority: int | None = None
    highest_priority: int | None = None

    def roll_priority(self, context: RebalanceContext) -> int:
        value = 0
        for _ in range(PRIORITY_BITS):
            value = (value << 1) | context.bits.bit()
        return value

    def target_depth(
        self,
        priority: int,
        lowest: int,
        highest: int,
        node_count: int,
        insertion_depth: int,
    ) -> int:
        """Choose the depth implied by the priority in the observed interval."""
        if priority < lowest:
            return 0

        if priority > highest:
            # Outside the known range: leave the new leaf where BST insertion put it.
            return insertion_depth

        if highest == lowest:
            return 0

        # Smallest number of levels whose perfect tree can hold node_count nodes:
        # 1 + 2 + ... + 2**(levels - 1) >= node_count.
        levels = 1
        while (1 << levels) - 1 < node_count:
            levels += 1

        # Divide [lowest, highest] into bands whose widths are proportional to
        # 1, 2, 4, ..., matching a perfect binary tree's level capacities.
        total_weight = (1 << levels) - 1
        span = highest - lowest
        position = priority - lowest

        cumulative = 0
        for depth in range(levels):
            band_width = span * (1 << depth) // total_weight
            cumulative += band_width
            if position < cumulative or depth == levels - 1:
                return depth

        return levels - 1

    def rebalance(self, context: RebalanceContext) -> None:
        priority = self.roll_priority(context)

        # State from before this insertion.
        node_count = self.inserted_count
        lowest = self.lowest_priority
        highest = self.highest_priority

        # Update the running summary after choosing the target depth.
        self.inserted_count += 1
        if lowest is None or priority < lowest:
            lowest = priority
        if highest is None or priority > highest:
            highest = priority
        self.lowest_priority = lowest
        self.highest_priority = highest

        context.stats.priority = priority

        node = context.inserted
        target = self.target_depth(
            priority,
            lowest,
            highest,
            node_count,
            context.stats.insertion_depth,
        )

        # Rotate upward until the node reaches its target depth.
        while self._current_depth(node) > target:
            context.promote(node, distance=0)

    @staticmethod
    def _current_depth(node) -> int:
        depth = 0
        while node.parent is not None:
            node = node.parent
            depth += 1
        return depth