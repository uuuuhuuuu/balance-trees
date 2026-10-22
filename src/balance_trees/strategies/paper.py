"""Stopping-rule baselines from Brodal, arXiv:2404.08287, Algorithms 1-2."""

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Protocol

from ..tree import Node
from .base import RebalanceContext


class RotationRule(Protocol):
    def apply(self, context: RebalanceContext, node: Node, distance: int) -> None: ...


@dataclass(frozen=True, slots=True)
class Zig:
    def apply(self, context: RebalanceContext, node: Node, distance: int) -> None:
        context.promote(node, distance)


@dataclass(frozen=True, slots=True)
class ZigZag:
    """Paper rule: promote the parent once in the straight case.

    In the bent case promote the selected node twice. This differs from the
    double zig-zig rotation in ordinary splaying. Do nothing at depth < 2.
    """

    def apply(self, context: RebalanceContext, node: Node, distance: int) -> None:
        parent = node.parent
        if parent is None or parent.parent is None:
            return
        grandparent = parent.parent
        straight = (parent.left is node) == (grandparent.left is parent)
        if straight:
            context.promote(parent, distance + 1)
        else:
            context.promote(node, distance)
            context.promote(node, distance)


@dataclass(frozen=True, slots=True)
class GeometricStop:
    """Walk on tails, apply one rule on heads, then stop (or stop at root)."""

    continue_probability: Fraction = Fraction(1, 2)
    rule: RotationRule = field(default_factory=Zig)

    def __post_init__(self) -> None:
        if not 0 <= self.continue_probability <= 1:
            raise ValueError("continue probability must be in [0, 1]")

    def rebalance(self, context: RebalanceContext) -> None:
        node = context.inserted
        distance = 0
        probability = self.continue_probability
        while node.parent is not None:
            if not context.choose(
                node, probability.numerator, probability.denominator, purpose="continue"
            ):
                self.rule.apply(context, node, distance)
                return
            node = node.parent
            distance += 1
