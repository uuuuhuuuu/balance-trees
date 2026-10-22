"""The single extension point that all rebalancing flavors implement."""

from dataclasses import dataclass
from typing import Protocol

from ..metrics import InsertionStats
from ..random_bits import RandomBits
from ..rotations import rotate_up
from ..tree import BST, Node


@dataclass(slots=True)
class RebalanceContext:
    tree: BST
    inserted: Node
    bits: RandomBits
    stats: InsertionStats
    seed: int = 0

    def scan(self, node: Node) -> None:
        """Count an actual node inspection for transient subtree reconstruction."""
        self.stats.scanned_nodes += 1

    def compare_priority(self, node: Node, priority: int, parent_priority: int) -> bool:
        """Compare recomputed priorities; no random bits or stored node fields."""
        if node.parent is None:
            raise ValueError("a root has no parent priority to compare")
        self.stats.visits += 1
        return (priority, node.key) < (parent_priority, node.parent.key)

    def choose(
        self, node: Node, numerator: int, denominator: int, *, purpose: str = "rotate"
    ) -> bool:
        """Count a decision and sample its coin; visual adapters may observe it."""
        self.stats.visits += 1
        return self.bits.bernoulli(numerator, denominator)

    def promote(self, node: Node, distance: int) -> None:
        """Apply one primitive rotation and record its original path distance."""
        rotate_up(self.tree, node)
        self.stats.rotation_distances.append(distance)


class Strategy(Protocol):
    def rebalance(self, context: RebalanceContext) -> None:
        """Rebalance after a successful leaf insertion."""
        ...


@dataclass(frozen=True, slots=True)
class NoRebalance:
    def rebalance(self, context: RebalanceContext) -> None:
        pass
