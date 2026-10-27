"""Versioned, renderer-independent traces of actual Python insertions."""

import re
from random import Random

from ..metrics import InsertionStats
from ..random_bits import RandomBits
from ..rotations import rotate_up
from ..strategies import STRATEGIES, create_strategy
from ..strategies.base import RebalanceContext
from ..tree import BST, Node

MAX_KEYS = 128
SAFE_INTEGER = 2**53 - 1


def parse_sequence(text: str) -> list[int]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Enter comma-separated integers, for example 8, 4, 12, 2.")
    parts = text.split(",")
    if len(parts) > MAX_KEYS:
        raise ValueError(f"Use at most {MAX_KEYS} keys for a readable animation.")
    result = []
    for index, part in enumerate(parts, 1):
        token = part.strip()
        if not re.fullmatch(r"[+-]?[0-9]+", token):
            raise ValueError(
                f"Item {index} is not an integer. Separate every number with a comma."
            )
        value = int(token)
        if abs(value) > SAFE_INTEGER:
            raise ValueError(
                f"Item {index} is outside the browser's safe integer range."
            )
        result.append(value)
    return result


class TraceRecorder:
    """Snapshot the tree after events, independently of any visual frontend.

    Full snapshots make backward stepping and third-party replay unambiguous.
    The showcase is bounded to small trees; none of this is benchmark work.
    """

    def __init__(
        self, tree: BST, bits: RandomBits, priorities: dict[int, int] | None = None
    ):
        self.tree = tree
        self.bits = bits
        self.priorities = priorities
        self.frames: list[dict] = []
        self.insertion = 0
        self.key: int | None = None
        self.stats = InsertionStats(False, 0)
        self.committed_rotations = 0
        self.committed_visits = 0
        self.committed_scans = 0
        self.seed = 0

    def capture(self, kind: str, title: str, description: str, **details) -> None:
        depths = self.tree.depths()
        nodes = []
        stack = [self.tree.root] if self.tree.root else []
        heap_valid = True
        while stack:
            node = stack.pop()
            priority = (
                self.priorities.get(node.key) if self.priorities is not None else None
            )
            nodes.append(
                {
                    "key": node.key,
                    "left": node.left.key if node.left else None,
                    "right": node.right.key if node.right else None,
                    "priority": priority,
                }
            )
            for child in (node.left, node.right):
                if child is not None:
                    stack.append(child)
                    if self.priorities is not None:
                        heap_valid &= (priority, node.key) <= (
                            self.priorities[child.key],
                            child.key,
                        )
        self.frames.append(
            {
                "kind": kind,
                "title": title,
                "description": description,
                "insertion": self.insertion,
                "key": self.key,
                "root": self.tree.root.key if self.tree.root else None,
                "nodes": sorted(nodes, key=lambda node: node["key"]),
                "heap_valid": heap_valid if self.priorities is not None else None,
                "stats": {
                    "nodes": len(nodes),
                    "height": max(depths.values(), default=0),
                    "mean_depth": sum(depths.values()) / len(depths) if depths else 0,
                    "rotations": self.committed_rotations + self.stats.rotations,
                    "visits": self.committed_visits + self.stats.visits,
                    "random_bits": self.bits.count,
                    "insertion_rotations": self.stats.rotations,
                    "scanned_nodes": self.committed_scans + self.stats.scanned_nodes,
                },
                **details,
            }
        )

    def rotation(self, node: Node, apply) -> None:
        parent = node.parent
        if parent is None:
            raise ValueError("cannot visualize promotion of a root")
        direction = "right" if parent.left is node else "left"
        middle = node.right if direction == "right" else node.left
        details = {
            "focus": node.key,
            "promoted": node.key,
            "demoted": parent.key,
            "direction": direction,
            "middle": middle.key if middle else None,
        }
        self.capture(
            "prepare",
            f"Prepare a {direction} rotation",
            f"Promote {node.key} over {parent.key}; the middle subtree keeps its key order.",
            **details,
        )
        apply()
        self.capture(
            "rotate",
            f"Rotate {direction}: {node.key} moves up",
            f"{parent.key} moves down. BST ordering is preserved while the links change.",
            **details,
        )


class TraceContext(RebalanceContext):
    """Observe strategy primitives without changing their decisions or randomness."""

    def __init__(self, recorder: TraceRecorder, node: Node):
        super().__init__(
            recorder.tree, node, recorder.bits, recorder.stats, recorder.seed
        )
        self.recorder = recorder

    def visit(self, node: Node) -> None:
        super().visit(node)
        self.recorder.capture(
            "visit",
            f"Inspect ancestor {node.key}",
            "Find the sampled repair level; repair a straight path once or a bent path twice.",
            focus=node.key,
        )

    def scan(self, node: Node) -> None:
        super().scan(node)
        self.recorder.capture(
            "scan",
            f"Count node {node.key}",
            "Inspect structure for a temporary subtree count; no size is saved in the node.",
            focus=node.key,
        )

    def compare_priority(self, node: Node, priority: int, parent_priority: int) -> bool:
        outcome = super().compare_priority(node, priority, parent_priority)
        self.recorder.capture(
            "priority",
            f"Recompute priorities at {node.key}",
            f"Key hash {priority:016x}; parent hash {parent_priority:016x}. "
            + ("Promote the child." if outcome else "Heap order holds; stop.")
            + " These values are discarded, not stored in the tree.",
            focus=node.key,
        )
        return outcome

    def choose(
        self, node: Node, numerator: int, denominator: int, *, purpose: str = "rotate"
    ) -> bool:
        outcome = super().choose(node, numerator, denominator, purpose=purpose)
        action = (
            purpose
            if outcome
            else ("skip rotation" if purpose == "rotate" else "rebalance here")
        )
        if purpose == "select-root":
            action = "select this subtree" if outcome else "keep the lower candidate"
        self.recorder.capture(
            "coin",
            f"Coin at {node.key}: {action}",
            f"Probability to {purpose}: {numerator}/{denominator}. "
            + (
                "The full walk continues upward after either outcome."
                if purpose == "rotate"
                else "Keep the highest successful ancestor, then promote the inserted key there."
                if purpose == "select-root"
                else "This policy stops at its first rebalance."
            ),
            focus=node.key,
            numerator=str(numerator),
            denominator=str(denominator),
            outcome=outcome,
            purpose=purpose,
        )
        return outcome

    def promote(self, node: Node, distance: int) -> None:
        self.recorder.rotation(
            node, lambda: super(TraceContext, self).promote(node, distance)
        )


def build_trace(values: list[int], strategy: str = "treap", seed: int = 2026) -> dict:
    """Treap reference or an unchanged registered Python strategy, frame by frame."""
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_KEYS:
        raise ValueError(f"Use a sequence of 1 to {MAX_KEYS} integer keys.")
    if any(type(key) is not int or abs(key) > SAFE_INTEGER for key in values):
        raise ValueError(
            "Keys must be integers inside the browser's safe integer range."
        )
    if strategy != "treap" and strategy not in STRATEGIES:
        raise ValueError("Unknown tree strategy.")
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("Seed must be an integer from 0 to 4294967295.")
    tree, bits = BST(), RandomBits(seed)
    priorities = {} if strategy == "treap" else None
    priority_random = Random(seed)
    recorder = TraceRecorder(tree, bits, priorities)
    recorder.seed = seed
    policy = create_strategy(strategy) if strategy != "treap" else None
    recorder.capture(
        "ready",
        "A tree starts with one decision",
        "Follow the search path, insert a leaf, then watch each rotation.",
    )
    for index, key in enumerate(values, 1):
        recorder.insertion, recorder.key = index, key
        recorder.stats = InsertionStats(False, 0)
        recorder.capture(
            "begin",
            f"Insert {key}",
            "Start at the root and follow the binary search rule.",
            focus=key,
        )
        current = tree.root
        while current is not None:
            relation = (
                "equal to"
                if key == current.key
                else "smaller than"
                if key < current.key
                else "larger than"
            )
            recorder.capture(
                "compare",
                f"Compare {key} with {current.key}",
                f"{key} is {relation} {current.key}. "
                + (
                    "Skip this duplicate."
                    if key == current.key
                    else "Continue left."
                    if key < current.key
                    else "Continue right."
                ),
                focus=current.key,
            )
            if key == current.key:
                break
            current = current.left if key < current.key else current.right
        result = tree.insert(key)
        recorder.stats = InsertionStats(result.inserted, result.depth)
        if result.inserted:
            if priorities is not None:
                priorities[key] = priority_random.getrandbits(32)
                # Priority generation consumes exactly 32 logical bits per node.
                bits.count += 32
            recorder.capture(
                "insert",
                f"Place {key} as a leaf",
                f"The search ends at depth {result.depth}. Now apply the selected balancing rule.",
                focus=key,
            )
            if priorities is not None:
                node = result.node
                while node.parent is not None:
                    parent = node.parent
                    recorder.stats.visits += 1
                    violation = (priorities[node.key], node.key) < (
                        priorities[parent.key],
                        parent.key,
                    )
                    recorder.capture(
                        "priority",
                        f"Compare priorities: {node.key} and {parent.key}",
                        "Smaller priorities belong higher in this min-heap. "
                        + (
                            "Rotate this child up."
                            if violation
                            else "The heap order holds; stop."
                        ),
                        focus=node.key,
                        demoted=parent.key,
                    )
                    if not violation:
                        break

                    def promote(node=node):
                        rotate_up(tree, node)
                        recorder.stats.rotation_distances.append(0)

                    recorder.rotation(node, promote)
            else:
                policy.rebalance(TraceContext(recorder, result.node))
        else:
            recorder.capture(
                "duplicate",
                f"{key} is already present",
                "Duplicate insertions leave the tree and random stream unchanged.",
                focus=key,
            )
        recorder.capture(
            "settled",
            f"Insertion {index} complete",
            f"{key} is in place. The tree is ready for the next key.",
            focus=key,
        )
        recorder.committed_rotations += recorder.stats.rotations
        recorder.committed_visits += recorder.stats.visits
        recorder.committed_scans += recorder.stats.scanned_nodes
        recorder.stats = InsertionStats(False, 0)
    return {
        "schema_version": 1,
        "strategy": strategy,
        "seed": seed,
        "sequence": values,
        "source": "python",
        "frames": recorder.frames,
    }
