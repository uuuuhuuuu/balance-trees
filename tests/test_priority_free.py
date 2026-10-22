"""Distribution and work bounds, beyond merely preserving BST ordering."""

import itertools
import unittest
from collections import Counter, defaultdict
from fractions import Fraction

from helpers import Decisions

from balance_trees import BST, Node, TreeFlavor
from balance_trees.strategies import HashPriority, RecountRoot, WindowRoot
from balance_trees.strategies.hashed import key_priority


def shape(node):
    return (node.key, shape(node.left), shape(node.right)) if node else None


def restore(value, parent=None):
    if value is None:
        return None
    node = Node(value[0], parent=parent)
    node.left = restore(value[1], node)
    node.right = restore(value[2], node)
    return node


class NeedCoin(Exception):
    def __init__(self, numerator, denominator):
        self.probability = Fraction(numerator, denominator)


class PartialCoins:
    count = 0

    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)

    def bernoulli(self, numerator, denominator):
        try:
            return next(self.outcomes)
        except StopIteration:
            raise NeedCoin(numerator, denominator) from None


def transitions(before, key):
    """Enumerate every coin outcome with its exact rational probability."""
    pending = [((), Fraction(1))]
    while pending:
        outcomes, probability = pending.pop()
        tree = BST()
        tree.root = restore(before)
        flavor = TreeFlavor(RecountRoot(), tree=tree, bits=PartialCoins(outcomes))
        try:
            stats = flavor.insert(key)
        except NeedCoin as coin:
            pending.append(((*outcomes, True), probability * coin.probability))
            pending.append(((*outcomes, False), probability * (1 - coin.probability)))
        else:
            yield shape(tree.root), probability, stats.rotations


class PriorityFreeTests(unittest.TestCase):
    def test_exact_lottery_matches_random_bst_shape_distribution(self):
        # Enumerate all outcomes: this is an exact check, not a frequency test.
        for n in (3, 4, 5):
            permutations = list(itertools.permutations(range(1, n + 1)))
            expected = Counter()
            for values in permutations:
                tree = BST()
                for key in values:
                    tree.insert(key)
                expected[shape(tree.root)] += Fraction(1, len(permutations))
            orders = (
                permutations
                if n < 5
                else [permutations[0], permutations[-1], (1, 5, 2, 4, 3)]
            )
            for values in orders:
                distribution = {None: Fraction(1)}
                for key in values:
                    updated = defaultdict(Fraction)
                    expected_rotations = Fraction(0)
                    for before, probability in distribution.items():
                        for after, conditional, rotations in transitions(before, key):
                            updated[after] += probability * conditional
                            expected_rotations += probability * conditional * rotations
                    distribution = updated
                    self.assertEqual(sum(distribution.values()), 1)
                    self.assertLess(expected_rotations, 2)
                self.assertEqual(dict(distribution), dict(expected), values)

    def test_recount_visits_every_existing_node_once_per_insertion(self):
        flavor = TreeFlavor(RecountRoot(), seed=2026)
        for n, key in enumerate([8, 4, 12, 2, 6, 10, 14, 0, -1], 1):
            stats = flavor.insert(key)
            self.assertEqual(stats.scanned_nodes, n)
            flavor.tree.depths()
        duplicate = flavor.insert(4)
        self.assertEqual(duplicate.scanned_nodes, 0)
        self.assertEqual(duplicate.random_bits, 0)

    def test_window_budget_bounds_inspections_and_rotations(self):
        for budget in (1, 2, 4, 16, 64):
            for values in (
                range(1, 257),
                [
                    value
                    for pair in zip(range(1, 129), range(256, 128, -1))
                    for value in pair
                ],
            ):
                flavor = TreeFlavor(WindowRoot(budget), seed=9)
                for key in values:
                    stats = flavor.insert(key)
                    self.assertLessEqual(stats.scanned_nodes, budget)
                    self.assertLessEqual(stats.rotations, budget - 1)
                    flavor.tree.depths()

    def test_incomplete_sibling_count_never_enters_a_lottery(self):
        tree = BST()
        for key in [8, 4, 12, 2, 6, 10, 14]:
            tree.insert(key)
        coins = Decisions([True])
        flavor = TreeFlavor(WindowRoot(3), tree=tree, bits=coins)
        stats = flavor.insert(1)
        self.assertEqual(coins.probabilities, [(1, 2)])
        self.assertEqual(stats.scanned_nodes, 3)
        self.assertEqual(stats.rotations, 1)
        self.assertEqual(tree.root.key, 8)
        tree.depths()

    def test_large_window_is_identical_to_exact_recount(self):
        exact = TreeFlavor(RecountRoot(), seed=42)
        window = TreeFlavor(WindowRoot(64), seed=42)
        for key in [1, 12, 2, 11, 3, 10, 4, 9, 5, 8, 6, 7]:
            self.assertEqual(exact.insert(key), window.insert(key))
            self.assertEqual(shape(exact.tree.root), shape(window.tree.root))

    def test_hash_heap_is_independent_of_insertion_order_for_fixed_seed(self):
        expected = None
        for values in itertools.permutations([-3, 0, 2, 9]):
            flavor = TreeFlavor(HashPriority(), seed=2026)
            for key in values:
                stats = flavor.insert(key)
                self.assertEqual(stats.random_bits, 0)
                self.assertEqual(stats.scanned_nodes, 0)
            actual = shape(flavor.tree.root)
            expected = actual if expected is None else expected
            self.assertEqual(actual, expected)
            stack = [flavor.tree.root]
            while stack:
                node = stack.pop()
                for child in (node.left, node.right):
                    if child:
                        self.assertLess(
                            (key_priority(node.key, 2026), node.key),
                            (key_priority(child.key, 2026), child.key),
                        )
                        stack.append(child)

    def test_hash_collisions_use_full_keys_and_add_no_node_fields(self):
        self.assertEqual(key_priority(0, 42), key_priority(2**64, 42))
        flavor = TreeFlavor(HashPriority(), seed=42)
        for key in [2**64, 0, -(2**64)]:
            flavor.insert(key)
        self.assertEqual(set(flavor.tree.depths()), {2**64, 0, -(2**64)})
        self.assertEqual(set(Node.__slots__), {"key", "left", "right", "parent"})
        self.assertEqual(BST.__slots__, ("root",))
        self.assertEqual(HashPriority.__slots__, ())
        self.assertEqual(RecountRoot.__slots__, ())

    def test_invalid_scan_budgets(self):
        for budget in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                WindowRoot(budget)
