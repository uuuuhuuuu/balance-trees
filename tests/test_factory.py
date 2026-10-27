import unittest

from balance_trees import BST, TreeFlavor
from balance_trees.strategies import (
    STRATEGIES,
    StrategyFactory,
    StrategySpec,
    TreapPriority,
    WindowRoot,
    create_strategy,
)


class StrategyFactoryTests(unittest.TestCase):
    def test_every_registered_strategy_gets_fresh_instances(self):
        for name in STRATEGIES:
            self.assertIsNot(create_strategy(name), create_strategy(name))

    def test_stateful_strategies_do_not_leak_across_trees(self):
        first = TreeFlavor.create("random-level", seed=42)
        second = TreeFlavor.create("random-level", seed=42)
        for key in range(12):
            first.insert(key)
        self.assertEqual(first.strategy.inserted_count, 12)
        self.assertEqual(second.strategy.inserted_count, 0)
        second.insert(7)
        self.assertEqual(second.strategy.inserted_count, 1)

    def test_factory_accepts_strategy_configuration(self):
        self.assertEqual(create_strategy("window-root", budget=7), WindowRoot(7))
        with self.assertRaises(ValueError):
            create_strategy("window-root", budget=0)
        with self.assertRaises(ValueError):
            create_strategy("typo")

    def test_random_level_versions_are_distinct_with_independent_state(self):
        original = TreeFlavor.create("random-level", seed=42)
        revised = TreeFlavor.create("random-level-v2", seed=42)
        self.assertIs(type(original.strategy), TreapPriority)
        self.assertIsNot(type(original.strategy), type(revised.strategy))
        for key in range(12):
            revised.insert(key)
        self.assertEqual(revised.strategy.inserted_count, 12)
        self.assertEqual(original.strategy.inserted_count, 0)

    def test_new_registration_requires_no_pipeline_change(self):
        factory = StrategyFactory()
        factory.register(
            "tiny-window",
            StrategySpec(lambda: WindowRoot(3), "Tiny window", "local", "Three scans"),
        )
        flavor = TreeFlavor(factory.create("tiny-window"), seed=1)
        for key in (4, 2, 6, 1, 3, 5, 7):
            self.assertLessEqual(flavor.insert(key).scanned_nodes, 3)
            flavor.tree.depths()
        self.assertEqual(factory.catalog()["tiny-window"]["name"], "Tiny window")
        with self.assertRaises(ValueError):
            factory.register("tiny-window", factory.specs["tiny-window"])


class PriorityStream:
    def __init__(self, *values):
        self.count = 0
        self.bits = iter(int(bit) for value in values for bit in f"{value:064b}")

    def bit(self):
        self.count += 1
        return next(self.bits)


class RandomLevelTests(unittest.TestCase):
    def test_sampled_depth_at_or_below_leaf_keeps_insertion_links_and_updates_state(self):
        for keys, key, depth in (
            ([0, -1, -2, -3, -4, -5, -6], 1, 1),
            ([0, 4, 3, 2, 1, -1, -2], 5, 2),
        ):
            with self.subTest(depth=depth):
                tree = BST()
                expected = BST()
                for value in keys:
                    tree.insert(value)
                    expected.insert(value)
                expected.insert(key)
                policy = TreapPriority(len(keys), 0, 70)
                self.assertEqual(policy.target_depth(30, 0, 70, 7, depth), 2)
                flavor = TreeFlavor(policy, tree=tree, bits=PriorityStream(30))
                stats = flavor.insert(key)
                self.assertEqual(stats.insertion_depth, depth)
                self.assertEqual(stats.rotations, 0)
                self.assertEqual(stats.visits, 0)
                self.assertEqual(stats.random_bits, 64)
                self.assertEqual(stats.rotation_distances, [])
                self.assertEqual(tree.depths(), expected.depths())
                self.assertTrue(tree.contains(key))
                self.assertEqual(policy.inserted_count, 8)
                self.assertEqual((policy.lowest_priority, policy.highest_priority), (0, 70))

    def test_shallower_sample_rotates_leaf_by_exact_depth_difference(self):
        for priority, target in ((0, 0), (10, 1), (30, 2)):
            with self.subTest(target=target):
                tree = BST()
                for key in range(7):
                    tree.insert(key)
                flavor = TreeFlavor(
                    TreapPriority(7, 0, 70), tree=tree, bits=PriorityStream(priority)
                )
                stats = flavor.insert(7)
                self.assertEqual(stats.insertion_depth, 7)
                self.assertEqual(stats.rotations, 7 - target)
                depths = tree.depths()
                self.assertEqual(depths[7], target)
                self.assertEqual(set(depths), set(range(8)))

    def test_new_minimum_uses_previous_interval_and_reaches_root(self):
        flavor = TreeFlavor(TreapPriority(), bits=PriorityStream(100, 200, 50))
        self.assertEqual(flavor.insert(1).random_bits, 64)
        # A new maximum stays at its initial depth, rather than being mapped
        # into the just-updated interval's last band.
        self.assertEqual(flavor.insert(2).rotations, 0)
        stats = flavor.insert(3)
        self.assertEqual(stats.rotations, 2)
        self.assertEqual(flavor.tree.root.key, 3)
        self.assertEqual(flavor.strategy.lowest_priority, 50)
        self.assertEqual(flavor.strategy.highest_priority, 200)
        flavor.tree.depths()

    def test_new_maximum_stays_at_deep_leaf_and_duplicates_preserve_state(self):
        flavor = TreeFlavor(TreapPriority(), bits=PriorityStream(10, 20, 30, 40))
        for key in range(1, 5):
            stats = flavor.insert(key)
            self.assertEqual(stats.rotations, 0)
            self.assertEqual(stats.random_bits, 64)
        self.assertEqual(flavor.tree.depths()[4], 3)
        self.assertFalse(flavor.insert(4).inserted)
        self.assertEqual(flavor.bits.count, 256)
        self.assertEqual(flavor.strategy.inserted_count, 4)

    def test_integer_bands_and_equal_interval(self):
        policy = TreapPriority()
        self.assertEqual(policy.target_depth(10, 10, 10, 1, 7), 0)
        self.assertEqual(policy.target_depth(21, 10, 20, 4, 7), 7)
        self.assertEqual(policy.target_depth(9, 10, 20, 4, 7), 0)
        self.assertEqual(
            [policy.target_depth(p, 0, 70, 4, 9) for p in (0, 9, 10, 29, 30, 70)],
            [0, 0, 1, 1, 2, 2],
        )
