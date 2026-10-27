"""A second random-level policy: local repairs plus rare record promotions."""

from dataclasses import dataclass

from .base import RebalanceContext
from .paper import ZigZag
from .random_level import TreapPriority

_LOCAL_REPAIR = ZigZag()


@dataclass(slots=True)
class RandomLevelV2(TreapPriority):
    """Sample a repair level instead of a final depth for the inserted leaf.

    State, interval bands and 64-bit rolls match the original policy. Ordinary
    insertions repair one path of length two, rather than promoting the leaf
    all the way to the sampled level. Strict new minima still reach the root.

    With k previous insertions, a strict record has probability <=1/(k+1) for
    iid uniform rolls and costs <=k rotations. Other insertions cost <=2, so
    E[R] < 3 per insertion from empty. This bound is over the whole priority
    history, not conditioned on an arbitrary existing tree. Ancestor walks can
    take O(h) work; no logarithmic-depth or treap-distribution claim is made.
    """

    def rebalance(self, context: RebalanceContext) -> None:
        priority = self.roll_priority(context)
        lowest, highest = self.lowest_priority, self.highest_priority
        depth = context.stats.insertion_depth
        target = (
            0
            if lowest is None
            else self.target_depth(
                priority, lowest, highest, self.inserted_count, depth
            )
        )
        is_record = lowest is not None and priority < lowest
        self.inserted_count += 1
        self.lowest_priority = priority if lowest is None else min(lowest, priority)
        self.highest_priority = priority if highest is None else max(highest, priority)
        context.stats.priority = priority

        node = context.inserted
        if is_record:
            for _ in range(depth):
                context.promote(node, distance=0)
            return
        if depth <= target:
            return
        if depth == target + 1:
            context.promote(node, distance=0)
            return

        # v1 spends h-target rotations on the leaf. Here we walk to the repair
        # instead. For a straight path promote its parent once; for a bend
        # promote its cursor twice. The chosen subtree root reaches target.
        distance = depth - target - 2
        for _ in range(distance):
            context.visit(node)
            node = node.parent
        context.visit(node)
        _LOCAL_REPAIR.apply(context, node, distance)
