"""Root-insertion lotteries with transient counts, never stored subtree sizes."""

from dataclasses import dataclass

from .base import RebalanceContext


def root_lottery(context: RebalanceContext, budget: int | None) -> None:
    """Keep the highest successful ancestor, then promote the leaf to its root.

    Ancestor sizes are assembled from disjoint off-path subtrees. An unlimited
    pass inspects each node exactly once. A capped pass stops before exceeding
    its budget and never substitutes an estimated count into an exact coin.
    """
    context.scan(context.inserted)
    child, size, selected = context.inserted, 1, None
    used = 1
    while child.parent is not None:
        if budget is not None and used == budget:
            break
        parent = child.parent
        context.scan(parent)
        used += 1
        sibling = parent.right if parent.left is child else parent.left
        stack = [sibling] if sibling else []
        sibling_size = 0
        while stack:
            if budget is not None and used == budget:
                break
            node = stack.pop()
            context.scan(node)
            used += 1
            sibling_size += 1
            if node.right is not None:
                stack.append(node.right)
            if node.left is not None:
                stack.append(node.left)
        if stack:  # This ancestor's subtree was not fully counted.
            break
        size += 1 + sibling_size
        if context.choose(parent, 1, size, purpose="select-root"):
            selected = parent
        child = parent
    if selected is not None:
        boundary = selected.parent
        while context.inserted.parent is not boundary:
            context.promote(context.inserted, distance=0)


@dataclass(frozen=True, slots=True)
class RecountRoot:
    """Exact random-BST insertion distribution, paying a full O(n) scan."""

    def rebalance(self, context: RebalanceContext) -> None:
        root_lottery(context, budget=None)


@dataclass(frozen=True, slots=True)
class WindowRoot:
    """Fixed structural scan budget; a local heuristic, not an exact treap."""

    budget: int = 64

    def __post_init__(self) -> None:
        if type(self.budget) is not int or self.budget < 1:
            raise ValueError("scan budget must be a positive integer")

    def rebalance(self, context: RebalanceContext) -> None:
        root_lottery(context, budget=self.budget)
