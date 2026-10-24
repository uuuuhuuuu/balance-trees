"""Strategy factories: add a name here to include a flavor in the CLI."""

from collections.abc import Callable
from fractions import Fraction

from .base import NoRebalance, RebalanceContext, Strategy
from .fixed import ConstantWalk, InverseDepthWalk
from .halving import HalvingWalk
from .hashed import HashPriority
from .lottery import RecountRoot, WindowRoot
from .paper import GeometricStop, Zig, ZigZag
from .random_level import TreapPriority

STRATEGIES: dict[str, Callable[[], Strategy]] = {
    "halving": HalvingWalk,
    "constant-half": ConstantWalk,
    "inverse-depth": InverseDepthWalk,
    "none": NoRebalance,
    "paper-zig": GeometricStop,
    "paper-zigzag": lambda: GeometricStop(Fraction(3, 4), ZigZag()),
    "recount-root": RecountRoot,
    "window-root": WindowRoot,
    "hash-priority": HashPriority,
    "random-level": TreapPriority,
}

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
    "WindowRoot",
    "Zig",
    "ZigZag",
    "random-level",
]
