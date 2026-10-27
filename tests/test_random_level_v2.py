import itertools
import json
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from helpers import FixedBits

from balance_trees import BST, RandomLevelV2, TreeFlavor
from balance_trees.measurement import run_trial
from balance_trees.sequences import ORDERS, insertion_order
from balance_trees.strategies import TreapPriority


def rolls(*values, bits=64):
    return FixedBits(int(bit) for value in values for bit in f"{value:0{bits}b}")


def prepared(keys, priority, *, lowest=0, highest=70):
    tree = BST()
    for key in keys:
        tree.insert(key)
    policy = RandomLevelV2(len(keys), lowest, highest)
    return TreeFlavor(policy, tree=tree, bits=rolls(priority))


class RandomLevelV2Tests(unittest.TestCase):
    def test_original_policy_reproduces_archived_trial_work_and_shape_metrics(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "src/balance_trees/showcase/site/dist/random-level-results/results.json"
        )
        original = json.loads(source.read_text())
        for order in ("random", "converging"):
            row = next(
                r
                for r in original["trials"]
                if r["n"] == 1000 and r["trial"] == 0 and r["order"] == order
            )
            actual = run_trial(
                insertion_order(order, 1000, row["order_seed"]),
                TreapPriority(),
                row["seed"],
            ).metrics
            for key, value in row["metrics"].items():
                if key not in ("seconds", "microseconds_per_insertion"):
                    self.assertEqual(getattr(actual, key), value, (order, key))

    def test_straight_repair_moves_an_ancestor_once_instead_of_lifting_the_leaf(self):
        flavor = prepared(range(7), 30)
        stats = flavor.insert(7)
        self.assertEqual(stats.insertion_depth, 7)
        self.assertEqual(stats.rotation_distances, [4])
        self.assertEqual(stats.visits, 4)
        depths = flavor.tree.depths()
        self.assertEqual(depths[3], 2)
        self.assertEqual(depths[7], 6)
        self.assertEqual(set(depths), set(range(8)))

    def test_bent_repair_promotes_the_selected_ancestor_twice(self):
        flavor = prepared([0, 8, 1, 7, 2, 6, 3], 30)
        stats = flavor.insert(4)
        self.assertEqual(stats.rotation_distances, [3, 3])
        self.assertEqual(stats.visits, 4)
        depths = flavor.tree.depths()
        self.assertEqual(depths[2], 2)
        self.assertEqual(set(depths), {0, 1, 2, 3, 4, 6, 7, 8})

    def test_a_leaf_one_edge_below_the_level_needs_one_rotation(self):
        flavor = prepared([0], 0)
        stats = flavor.insert(1)
        self.assertEqual(stats.rotation_distances, [0])
        self.assertEqual(flavor.tree.root.key, 1)

    def test_strict_new_minimum_can_still_use_more_than_two_rotations(self):
        flavor = prepared(range(20), 50, lowest=100, highest=200)
        stats = flavor.insert(20)
        self.assertEqual(stats.rotations, 20)
        self.assertEqual(flavor.tree.root.key, 20)
        self.assertEqual(flavor.strategy.lowest_priority, 50)
        self.assertEqual(len(flavor.tree.depths()), 21)

    def test_equal_priorities_are_not_strict_records(self):
        flavor = prepared(range(20), 10, lowest=10, highest=10)
        stats = flavor.insert(20)
        self.assertEqual(stats.rotations, 1)
        self.assertNotEqual(flavor.tree.root.key, 20)
        self.assertEqual(len(flavor.tree.depths()), 21)

    def test_new_maximum_and_shallow_insertions_leave_the_leaf_in_place(self):
        flavor = prepared(range(7), 71)
        self.assertEqual(flavor.insert(7).rotations, 0)
        self.assertEqual(flavor.tree.depths()[7], 7)
        shallow = prepared([0, 3, 2, 1, -1, -2, -3], 70)
        self.assertEqual(shallow.insert(4).rotations, 0)
        self.assertEqual(shallow.tree.depths()[4], 2)

    def test_empty_tree_duplicates_bits_and_state_are_unchanged(self):
        flavor = TreeFlavor(RandomLevelV2(), bits=rolls(100, 200))
        self.assertEqual(flavor.tree.depths(), {})
        first = flavor.insert(-1)
        self.assertEqual(first.rotations, 0)
        self.assertEqual(first.random_bits, 64)
        duplicate = flavor.insert(-1)
        self.assertFalse(duplicate.inserted)
        self.assertEqual(duplicate.random_bits, 0)
        self.assertEqual(flavor.strategy.inserted_count, 1)
        self.assertEqual(flavor.strategy.lowest_priority, 100)
        self.assertEqual(flavor.strategy.highest_priority, 100)
        self.assertTrue(flavor.tree.contains(-1))
        flavor.insert(2)
        self.assertEqual(flavor.bits.count, 128)

    def test_finite_priority_histories_have_constant_expected_rotation_bound(self):
        # Exhaust the finite model, including ties; this is not a frequency test.
        for values in ([0, 1, 2, 3, 4, 5], [0, 5, 1, 4, 2, 3]):
            totals = [0] * len(values)
            with patch("balance_trees.strategies.random_level.PRIORITY_BITS", 2):
                for priorities in itertools.product(range(4), repeat=len(values)):
                    flavor = TreeFlavor(
                        RandomLevelV2(), bits=rolls(*priorities, bits=2)
                    )
                    for index, (key, priority) in enumerate(zip(values, priorities)):
                        stats = flavor.insert(key)
                        if index and priority < min(priorities[:index]):
                            self.assertLessEqual(stats.rotations, index)
                        else:
                            self.assertLessEqual(stats.rotations, 2)
                        totals[index] += stats.rotations
                    self.assertEqual(set(flavor.tree.depths()), set(values))
            for index, total in enumerate(totals):
                self.assertLessEqual(
                    Fraction(total, 4 ** len(values)), 2 + Fraction(index, index + 1)
                )

    def test_all_input_families_preserve_keys_and_nonrecord_rotation_bound(self):
        for order in ORDERS:
            flavor = TreeFlavor.create("random-level-v2", seed=2026)
            values = insertion_order(order, 1024, 2026)
            for index, key in enumerate(values):
                low = flavor.strategy.lowest_priority
                stats = flavor.insert(key)
                self.assertEqual(stats.random_bits, 64)
                if low is None or stats.priority >= low:
                    self.assertLessEqual(stats.rotations, 2)
                if index % 64 == 0:
                    flavor.tree.depths()
            self.assertEqual(set(flavor.tree.depths()), set(values))
