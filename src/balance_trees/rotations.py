"""Structural rotations, independent of strategies and instrumentation."""

from .tree import BST, Node


def rotate_up(tree: BST, node: Node) -> None:
    """Promote node over its parent and reconnect the middle subtree and root."""
    parent = node.parent
    if parent is None:
        raise ValueError("cannot rotate the root up")
    grandparent = parent.parent
    if grandparent is not None and not (
        grandparent.left is parent or grandparent.right is parent
    ):
        raise ValueError("parent is not linked from its parent")
    if parent.left is node:
        parent.left = node.right
        if node.right is not None:
            node.right.parent = parent
        node.right = parent
    elif parent.right is node:
        parent.right = node.left
        if node.left is not None:
            node.left.parent = parent
        node.left = parent
    else:
        raise ValueError("node is not linked from its parent")
    node.parent = grandparent
    parent.parent = node
    if grandparent is None:
        tree.root = node
    elif grandparent.left is parent:
        grandparent.left = node
    else:
        grandparent.right = node


def rotate_left(tree: BST, pivot: Node) -> None:
    """Promote the pivot's right child."""
    if pivot.right is None:
        raise ValueError("left rotation requires a right child")
    rotate_up(tree, pivot.right)


def rotate_right(tree: BST, pivot: Node) -> None:
    """Promote the pivot's left child."""
    if pivot.left is None:
        raise ValueError("right rotation requires a left child")
    rotate_up(tree, pivot.left)
