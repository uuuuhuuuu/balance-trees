"""Compose the plain tree, a strategy and an external random-bit source."""

from .metrics import InsertionStats
from .random_bits import RandomBits
from .strategies.base import NoRebalance, RebalanceContext, Strategy
from .tree import BST


class TreeFlavor:
    """A reusable insertion pipeline; adding strategies never changes BST."""

    @classmethod
    def create(cls, name: str, *, seed: int = 0, **options) -> "TreeFlavor":
        from .strategies import create_strategy

        return cls(create_strategy(name, **options), seed=seed)

    def __init__(
        self,
        strategy: Strategy | None = None,
        *,
        seed: int = 0,
        tree: BST | None = None,
        bits: RandomBits | None = None,
    ) -> None:
        self.tree = tree if tree is not None else BST()
        self.strategy = strategy if strategy is not None else NoRebalance()
        self.bits = bits if bits is not None else RandomBits(seed)
        self.seed = seed

    def insert(self, key: int) -> InsertionStats:
        result = self.tree.insert(key)
        stats = InsertionStats(result.inserted, result.depth)
        if result.inserted:
            before = self.bits.count
            self.strategy.rebalance(
                RebalanceContext(self.tree, result.node, self.bits, stats, self.seed)
            )
            stats.random_bits = self.bits.count - before
        return stats

    def __str__(self) -> str:
        return str(self.tree)
