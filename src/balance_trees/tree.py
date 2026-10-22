"""A plain, iterative BST with no knowledge of balancing or randomness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, eq=False)
class Node:
    """Only the element and structural pointers persist in each node."""

    key: int
    left: Node | None = None
    right: Node | None = None
    parent: Node | None = None


@dataclass(frozen=True, slots=True)
class InsertResult:
    node: Node
    inserted: bool
    depth: int


class BST:
    __slots__ = ("root",)

    def __init__(self) -> None:
        self.root: Node | None = None

    def insert(self, key: int) -> InsertResult:
        """Insert a new leaf. Duplicate keys leave the tree unchanged."""
        parent = None
        current = self.root
        depth = 0
        while current is not None:
            if key == current.key:
                return InsertResult(current, False, depth)
            parent = current
            current = current.left if key < current.key else current.right
            depth += 1
        node = Node(key, parent=parent)
        if parent is None:
            self.root = node
        elif key < parent.key:
            parent.left = node
        else:
            parent.right = node
        return InsertResult(node, True, depth)

    def contains(self, key: int) -> bool:
        current = self.root
        while current is not None:
            if current.key == key:
                return True
            current = current.left if key < current.key else current.right
        return False

    def depths(self) -> dict[int, int]:
        """Validate ordering, links and acyclicity; return depths for analysis.

        This O(n) analysis is separate from insertion and rebalancing costs.
        """
        result: dict[int, int] = {}
        seen: set[int] = set()
        stack = [(self.root, None, None, None, 0)]
        while stack:
            node, parent, lower, upper, depth = stack.pop()
            if node is None:
                continue
            if id(node) in seen:
                raise AssertionError("cycle or shared child")
            seen.add(id(node))
            if node.parent is not parent:
                raise AssertionError("inconsistent parent link")
            if lower is not None and node.key <= lower:
                raise AssertionError("BST lower bound violated")
            if upper is not None and node.key >= upper:
                raise AssertionError("BST upper bound violated")
            result[node.key] = depth
            stack.append((node.right, node, node.key, upper, depth + 1))
            stack.append((node.left, node, lower, node.key, depth + 1))
        return result

    def __str__(self) -> str:
        from .rendering import render_tree

        return render_tree(self)
