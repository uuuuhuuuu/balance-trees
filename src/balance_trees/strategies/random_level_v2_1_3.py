"""Random-level v2.1.3: geometric target levels with direct leaf promotion."""

from dataclasses import dataclass

from .base import RebalanceContext
from .random_level import TreapPriority


@dataclass(slots=True)
class RandomLevelV213(TreapPriority):
    """Choose a target level from the top, then promote the inserted leaf.

    For insertion k, let n=k including the new vertex and set
    max=ceil(log2(n)). Count consecutive 1-bits into move, stopping at the
    first 0 or when move reaches max. The target depth is max-move.

    If the inserted leaf's depth d exceeds that target, promote the leaf
    exactly d-target times. There are no stored extrema, no special minimum or
    maximum case, and no v2-style local repair.
    """

    def rebalance(self, context: RebalanceContext) -> None:
        n = self.inserted_count + 1
        maximum = max(0, (n - 1).bit_length())
        move = 0
        while move < maximum and context.bits.bit():
            move += 1

        target = maximum - move
        depth = context.stats.insertion_depth
        self.inserted_count += 1
        context.stats.priority = move

        if depth <= target:
            return

        node = context.inserted
        for _ in range(depth - target):
            context.promote(node, distance=0)
