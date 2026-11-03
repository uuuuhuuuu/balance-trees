"""v2.1.1: v2 local repairs with fixed virtual priority extrema.

With n previous successful insertions, roll (n+1).bit_length() bits.
Only all-zero rolls promote the leaf to the root; all-one rolls do nothing.
Interior rolls use the existing integer target bands with virtual bounds
1 and 2**bits-2. No observed extrema or priorities are retained.

Use TreeFlavor(RandomLevelV211(), seed=2026). This module does not change
the browser implementation or the global CLI strategy catalog.
"""

from dataclasses import dataclass

from .base import RebalanceContext
from .paper import ZigZag
from .random_level import TreapPriority

_REPAIR = ZigZag()


@dataclass(slots=True)
class RandomLevelV211:
    inserted_count: int = 0

    def rebalance(self, context: RebalanceContext) -> None:
        n = self.inserted_count
        width = max(1, (n + 1).bit_length())
        priority = 0
        for _ in range(width):
            priority = (priority << 1) | context.bits.bit()
        self.inserted_count += 1
        context.stats.priority = priority
        depth = context.stats.insertion_depth
        node = context.inserted
        if priority == 0:
            for _ in range(depth):
                context.promote(node, distance=0)
            return
        maximum = (1 << width) - 1
        if priority == maximum:
            return
        # Only root insertion has width=1, so interior rolls have valid bounds.
        # target_depth currently uses only its arguments, not the receiver.
        target = TreapPriority.target_depth(
            self, priority, 1, maximum - 1, n, depth
        )
        if depth <= target:
            return
        if depth == target + 1:
            context.promote(node, distance=0)
            return
        distance = depth - target - 2
        for _ in range(distance):
            context.visit(node)
            node = node.parent
        context.visit(node)
        _REPAIR.apply(context, node, distance)
