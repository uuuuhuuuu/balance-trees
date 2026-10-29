"""Hybrid of v2 local repair and v3 final-depth promotion."""

import math
from dataclasses import dataclass

from .base import RebalanceContext
from .random_level_v2 import RandomLevelV2
from .random_level_v3 import RandomLevelV3


@dataclass(slots=True)
class RandomLevelV4(RandomLevelV3):
    """Use v2 for d < ln(n), otherwise v3; n counts previous insertions.

    Equality and the empty-tree case use v3. Both branches operate on this
    same state, so each successful insertion rolls once and updates extrema
    and count once. V2's record rule applies only in its selected branch.
    No balance or expected-cost theorem is claimed for this hybrid.
    """

    def rebalance(self, context: RebalanceContext) -> None:
        if (
            self.inserted_count > 0
            and context.stats.insertion_depth < math.log(self.inserted_count)
        ):
            RandomLevelV2.rebalance(self, context)
        else:
            RandomLevelV3.rebalance(self, context)
