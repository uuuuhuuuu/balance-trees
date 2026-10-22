"""Treap-style priorities recomputed from keys; no priority table is retained."""

from dataclasses import dataclass

from .base import RebalanceContext

MASK64 = (1 << 64) - 1


def key_priority(key: int, seed: int) -> int:
    """SplitMix64 mixing of key XOR seed, reduced modulo 2**64.

    This is a deterministic finite hash, not independent random priorities.
    Keys congruent modulo 2**64 collide; the full key breaks priority ties.
    Mixer: https://xorshift.di.unimi.it/splitmix64.c (public domain).
    """
    value = ((key ^ seed) + 0x9E3779B97F4A7C15) & MASK64
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
    return value ^ (value >> 31)


@dataclass(frozen=True, slots=True)
class HashPriority:
    """Recompute the new key and ancestor priorities; rotate until heap order."""

    def rebalance(self, context: RebalanceContext) -> None:
        node = context.inserted
        priority = key_priority(node.key, context.seed)
        while node.parent is not None:
            parent_priority = key_priority(node.parent.key, context.seed)
            if not context.compare_priority(node, priority, parent_priority):
                break
            context.promote(node, distance=0)
