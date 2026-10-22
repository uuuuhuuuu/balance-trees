"""Strategy factories: add a name here to include a flavor in the CLI."""

from collections.abc import Callable
from fractions import Fraction

from .base import NoRebalance, RebalanceContext, Strategy
from .fixed import ConstantWalk, InverseDepthWalk
from .halving import HalvingWalk
from .paper import GeometricStop, Zig, ZigZag

STRATEGIES: dict[str, Callable[[], Strategy]] = {
    "halving": HalvingWalk,
    "constant-half": ConstantWalk,
    "inverse-depth": InverseDepthWalk,
    "none": NoRebalance,
    "paper-zig": GeometricStop,
    "paper-zigzag": lambda: GeometricStop(Fraction(3, 4), ZigZag()),
}

__all__ = [
    "STRATEGIES",
    "ConstantWalk",
    "GeometricStop",
    "HalvingWalk",
    "InverseDepthWalk",
    "NoRebalance",
    "RebalanceContext",
    "Strategy",
    "Zig",
    "ZigZag",
]
