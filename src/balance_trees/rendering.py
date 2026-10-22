"""Readable, bounded tree diagrams, including for degenerate trees."""

from .tree import BST


def render_tree(
    tree: BST, *, max_depth: int = 8, max_nodes: int = 100, ascii_only: bool = False
) -> str:
    """Print labelled left/right branches; limits prevent runaway output."""
    if max_depth < 0 or max_nodes < 1:
        raise ValueError("max_depth must be nonnegative and max_nodes positive")
    if tree.root is None:
        return "<empty>"
    branch, last_branch, vertical, gap = (
        ("|-- ", "`-- ", "|   ", "    ")
        if ascii_only
        else ("├── ", "└── ", "│   ", "    ")
    )
    ellipsis = "..." if ascii_only else "…"
    lines = []
    seen: set[int] = set()
    stack = [(tree.root, "", "", 0, True)]
    while stack:
        node, prefix, label, depth, is_last = stack.pop()
        connector = (last_branch if is_last else branch) if depth else ""
        if len(seen) >= max_nodes:
            lines.append(prefix + connector + ellipsis + " (node limit)")
            break
        if id(node) in seen:
            raise ValueError("cannot render a cycle or shared child")
        seen.add(id(node))
        lines.append(
            prefix + connector + (label + ": " if label else "") + str(node.key)
        )
        child_prefix = prefix + (gap if is_last else vertical) if depth else ""
        children = [("L", node.left), ("R", node.right)]
        children = [(side, child) for side, child in children if child is not None]
        if depth == max_depth and children:
            lines.append(child_prefix + last_branch + ellipsis + " (depth limit)")
            continue
        for index in range(len(children) - 1, -1, -1):
            side, child = children[index]
            stack.append(
                (child, child_prefix, side, depth + 1, index == len(children) - 1)
            )
    return "\n".join(lines)
