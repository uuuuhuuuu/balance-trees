"""Full upward walks whose coin probability is fixed for each insertion."""

from dataclasses import dataclass
from fractions import Fraction
from itertools import repeat

from .base import RebalanceContext
from .walk import walk_up


@dataclass(frozen=True, slots=True)
class ConstantWalk:
    """Try the same rotation probability at every decision; default is 1/2."""

    rotation_probability: Fraction = Fraction(1, 2)

    def __post_init__(self) -> None:
        if not 0 <= self.rotation_probability <= 1:
            raise ValueError("rotation probability must be in [0, 1]")

    def rebalance(self, context: RebalanceContext) -> None:
        probability = self.rotation_probability
        walk_up(context, repeat((probability.numerator, probability.denominator)))


@dataclass(frozen=True, slots=True)
class InverseDepthWalk:
    """Use 1/h at every decision, with h the leaf's initial insertion depth.

    Freeze h before rebalancing; do not update it after rotations or ascent.
    A root insertion has no ancestors and therefore needs no coin or division.
    This deliberately uses nonlocal insertion-path information.
    """

    def rebalance(self, context: RebalanceContext) -> None:
        depth = context.stats.insertion_depth
        if depth == 0:
            return
        walk_up(context, repeat((1, depth)))
