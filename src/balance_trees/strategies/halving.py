"""The experimental full upward walk with geometrically decreasing coins."""

from dataclasses import dataclass
from itertools import count

from .base import RebalanceContext
from .walk import walk_up


@dataclass(frozen=True, slots=True)
class HalvingWalk:
    """Decision k rotates with probability 2**(-k-1); always continue upward.

    After promotion, move to the promoted node's new parent. Thus a success
    skips the demoted parent: k counts decisions, not original path edges.
    No size, depth or other balance information is consulted.
    """

    def rebalance(self, context: RebalanceContext) -> None:
        walk_up(context, ((1, 1 << exponent) for exponent in count(1)))
