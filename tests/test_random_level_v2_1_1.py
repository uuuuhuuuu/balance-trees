import itertools
import unittest

from balance_trees import BST, TreeFlavor
from balance_trees.metrics import InsertionStats
from balance_trees.strategies.base import RebalanceContext
from balance_trees.strategies.random_level_v2 import RandomLevelV2
from balance_trees.strategies.random_level_v2_1_1 import RandomLevelV211


class Bits:
    def __init__(self, priority, width):
        self.values = iter(map(int, format(priority, f'0{width}b')))
        self.count = 0

    def bit(self):
        value = next(self.values)
        self.count += 1
        return value


def snapshot(tree):
    result = {}
    stack = [tree.root] if tree.root else []
    while stack:
        node = stack.pop()
        result[node.key] = (node.left.key if node.left else None, node.right.key if node.right else None)
        stack.extend(child for child in (node.left, node.right) if child)
    return result


def apply(strategy, keys, key, priority, width):
    tree = BST()
    for value in keys:
        tree.insert(value)
    inserted = tree.insert(key)
    stats = InsertionStats(True, inserted.depth)
    bits = Bits(priority, width)
    strategy.rebalance(RebalanceContext(tree, inserted.node, bits, stats))
    tree.depths()
    return tree, stats, bits


class V211Tests(unittest.TestCase):
    def test_zero_roll_promotes_to_root(self):
        tree, stats, bits = apply(RandomLevelV211(7), range(7), 7, 0, 4)
        self.assertEqual(tree.root.key, 7)
        self.assertEqual(stats.rotations, 7)
        self.assertEqual(bits.count, 4)

    def test_all_ones_keeps_leaf_and_does_not_store_extrema(self):
        strategy = RandomLevelV211(7)
        tree, stats, bits = apply(strategy, range(7), 7, 15, 4)
        self.assertEqual(tree.depths()[7], 7)
        self.assertEqual(stats.rotations, 0)
        self.assertEqual(bits.count, 4)
        self.assertFalse(hasattr(strategy, 'lowest_priority'))
        self.assertFalse(hasattr(strategy, 'highest_priority'))
        self.assertEqual(strategy.inserted_count, 8)

    def test_every_roll_matches_v2_with_virtual_bounds(self):
        class Reference(RandomLevelV2):
            def roll_priority(self, context):
                value = 0
                for _ in range((self.inserted_count + 1).bit_length()):
                    value = (value << 1) | context.bits.bit()
                return value
        paths = [([0, 2, 4, 6, 8, 10, 12], 14), ([14, 12, 10, 8, 6, 4, 2], 0), ([8, 2, 12, 4, 10, 6, 3], 5)]
        for keys, key in paths:
            for priority in range(16):
                with self.subTest(keys=keys, priority=priority):
                    actual = apply(RandomLevelV211(7), keys, key, priority, 4)
                    expected = apply(Reference(7, 1, 14), keys, key, priority, 4)
                    self.assertEqual(snapshot(actual[0]), snapshot(expected[0]))
                    self.assertEqual(actual[1].rotation_distances, expected[1].rotation_distances)
                    self.assertEqual(actual[1].visits, expected[1].visits)
                    self.assertEqual(actual[1].priority, priority)

    def test_width_boundaries_and_duplicates(self):
        strategy = RandomLevelV211()
        flavor = TreeFlavor(strategy, seed=2026)
        for n in range(130):
            stats = flavor.insert(n)
            self.assertEqual(stats.random_bits, (n + 1).bit_length())
            self.assertEqual(strategy.inserted_count, n + 1)
            duplicate = flavor.insert(n)
            self.assertFalse(duplicate.inserted)
            self.assertEqual(duplicate.random_bits, 0)
            self.assertEqual(strategy.inserted_count, n + 1)
            self.assertEqual(len(flavor.tree.depths()), n + 1)

    def test_root_handles_both_one_bit_outcomes(self):
        for priority in (0, 1):
            tree, stats, bits = apply(RandomLevelV211(), [], 5, priority, 1)
            self.assertEqual(tree.root.key, 5)
            self.assertEqual(stats.rotations, 0)
            self.assertEqual(bits.count, 1)

    def test_permutations_preserve_invariants_and_rotation_limits(self):
        for keys in itertools.permutations(range(5)):
            for seed in (0, 9):
                flavor = TreeFlavor(RandomLevelV211(), seed=seed)
                for n, key in enumerate(keys):
                    stats = flavor.insert(key)
                    self.assertEqual(len(flavor.tree.depths()), n + 1)
                    if stats.priority == 0:
                        self.assertEqual(stats.rotations, stats.insertion_depth)
                    elif stats.priority == (1 << (n + 1).bit_length()) - 1:
                        self.assertEqual(stats.rotations, 0)
                    else:
                        self.assertLessEqual(stats.rotations, 2)


if __name__ == '__main__':
    unittest.main()
