"""Conventional insertion-only treap: BST keys and stored min-heap priorities.

Usage: tree = Treap(seed=2026); stats = tree.insert(key).
stats.insertion_depth is measured BEFORE rotations. Duplicate keys are no-ops.
64-bit pseudorandom priorities use the key as a deterministic tie-breaker.
This baseline intentionally stores metadata unlike the priority-free strategies.
It is not registered as a priority-free Strategy.
"""

from dataclasses import dataclass
from random import Random

from .metrics import InsertionStats
from .rotations import rotate_up
from .tree import BST, Node


@dataclass(slots=True, eq=False)
class TreapNode(Node):
    priority: int = 0


class Treap(BST):
    """Iterative set insertion and lookup; no deletion API."""

    __slots__ = ("_random",)

    def __init__(self, seed: int = 0) -> None:
        super().__init__()
        self._random = Random(seed)

    def insert(self, key: int) -> InsertionStats:
        parent = None
        current = self.root
        depth = 0
        while current is not None:
            if key == current.key:
                return InsertionStats(False, depth)
            parent = current
            current = current.left if key < current.key else current.right
            depth += 1
        priority = self._random.getrandbits(64)
        node = TreapNode(key, parent=parent, priority=priority)
        if parent is None:
            self.root = node
        elif key < parent.key:
            parent.left = node
        else:
            parent.right = node
        stats = InsertionStats(True, depth, random_bits=64, priority=priority)
        while node.parent is not None:
            stats.visits += 1
            parent = node.parent
            if (node.priority, node.key) >= (parent.priority, parent.key):
                break
            rotate_up(self, node)
            stats.rotation_distances.append(0)
        return stats

    def validate(self) -> dict[int, int]:
        """Check BST order, links, reachability cycles, and priority heap order.

        Returns key depths. O(n) diagnostic work, not insertion work.
        """
        depths = super().depths()
        stack = [self.root] if self.root is not None else []
        while stack:
            node = stack.pop()
            for child in (node.left, node.right):
                if child is not None:
                    if (child.priority, child.key) < (node.priority, node.key):
                        raise AssertionError("treap heap order violated")
                    stack.append(child)
        return depths
