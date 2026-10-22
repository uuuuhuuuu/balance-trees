"""Shared traversal for strategies that keep walking after every outcome."""

from collections.abc import Iterator

from .base import RebalanceContext


def walk_up(
    context: RebalanceContext, probabilities: Iterator[tuple[int, int]]
) -> None:
    """Consume one exact coin per decision until the current cursor is root.

    Supply an unbounded stream of (numerator, denominator) probabilities.
    After a promotion, the new parent is the next cursor, so the demoted old
    parent is skipped. Distances refer to the original insertion path.
    """
    node = context.inserted
    distance = 0
    while node.parent is not None:
        numerator, denominator = next(probabilities)
        if context.choose(node, numerator, denominator):
            context.promote(node, distance)
            distance += 1
        parent = node.parent
        if parent is None:
            return
        node = parent
        distance += 1
