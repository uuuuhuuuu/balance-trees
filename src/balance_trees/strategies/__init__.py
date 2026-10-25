"""Strategy factories: add a name here to include a flavor in the CLI."""

from fractions import Fraction

from .base import NoRebalance, RebalanceContext, Strategy
from .fixed import ConstantWalk, InverseDepthWalk
from .halving import HalvingWalk
from .hashed import HashPriority
from .lottery import RecountRoot, WindowRoot
from .paper import GeometricStop, Zig, ZigZag
from .random_level import TreapPriority
from .registry import StrategyFactory, StrategySpec

strategy_factory = StrategyFactory()
for identifier, spec in {
    "halving": StrategySpec(
        HalvingWalk,
        "Halving walk",
        "Full upward walk",
        "Try 1/2, 1/4, 1/8… and continue to the root after either outcome. Expected fewer than one rotation per insertion; ancestor work can be linear.",
    ),
    "constant-half": StrategySpec(
        ConstantWalk,
        "Constant ½",
        "Full upward walk",
        "Rotate with probability 1/2 at every visited ancestor, continuing to the root. Both visits and rotations can grow with depth.",
    ),
    "inverse-depth": StrategySpec(
        InverseDepthWalk,
        "Inverse depth",
        "Depth-informed rule",
        "Freeze initial insertion depth h and use 1/h at every decision. Sorted inputs produce a chain despite at most one expected rotation.",
    ),
    "none": StrategySpec(
        NoRebalance,
        "Plain BST",
        "No rebalancing",
        "Ordinary leaf insertion. Ordered inputs can produce linear height and quadratic insertion work.",
    ),
    "paper-zig": StrategySpec(
        GeometricStop,
        "Paper · Zig",
        "Geometric stop",
        "Continue upward with probability 1/2; otherwise promote the cursor once and stop.",
    ),
    "paper-zigzag": StrategySpec(
        lambda: GeometricStop(Fraction(3, 4), ZigZag()),
        "Paper · ZigZag",
        "Geometric stop",
        "Continue with probability 3/4. On stopping, a straight path promotes the parent once, a bent path promotes the cursor twice.",
    ),
    "recount-root": StrategySpec(
        RecountRoot,
        "Recount root lottery",
        "Exact distribution",
        "Exact random-BST shape distribution from empty, using transient full-tree counting. Linear scan work per insertion; quadratic total scans.",
    ),
    "window-root": StrategySpec(
        WindowRoot,
        "Window root lottery",
        "Bounded local heuristic",
        "Root lotteries within 64 actual node inspections by default. Never uses an incomplete count; no general logarithmic-depth guarantee.",
    ),
    "hash-priority": StrategySpec(
        HashPriority,
        "Recomputed priority",
        "Keyed hash heuristic",
        "Recompute SplitMix64 key/seed priorities for treap-style comparisons. No priority table or fresh insertion bits; finite hashes are not independent priorities.",
    ),
    "random-level": StrategySpec(
        TreapPriority,
        "Random level",
        "Priority-free depth heuristic",
        "Roll 64 fair bits and choose a depth from the previous observed priority interval. New minima reach the root; new maxima stay leaves. Stores only a count and two extrema; no balance guarantee.",
    ),
}.items():
    strategy_factory.register(identifier, spec)

# Backwards-compatible iterable of callable descriptors.
STRATEGIES = strategy_factory.specs
create_strategy = strategy_factory.create

__all__ = [
    "STRATEGIES",
    "ConstantWalk",
    "GeometricStop",
    "HalvingWalk",
    "HashPriority",
    "InverseDepthWalk",
    "NoRebalance",
    "RebalanceContext",
    "RecountRoot",
    "Strategy",
    "StrategyFactory",
    "StrategySpec",
    "TreapPriority",
    "WindowRoot",
    "Zig",
    "ZigZag",
    "create_strategy",
    "strategy_factory",
]
