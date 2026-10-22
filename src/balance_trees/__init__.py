"""Composable, metadata-free binary search tree experiments."""

from .flavors import TreeFlavor
from .graphviz import render_graphviz, to_dot, write_dot
from .rendering import render_tree
from .strategies import (
    ConstantWalk,
    GeometricStop,
    HalvingWalk,
    InverseDepthWalk,
    NoRebalance,
    Zig,
    ZigZag,
)
from .tree import BST, Node

__all__ = [
    "BST",
    "ConstantWalk",
    "GeometricStop",
    "HalvingWalk",
    "InverseDepthWalk",
    "NoRebalance",
    "Node",
    "TreeFlavor",
    "Zig",
    "ZigZag",
    "render_graphviz",
    "render_tree",
    "to_dot",
    "write_dot",
]
