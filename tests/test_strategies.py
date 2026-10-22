import itertools
import unittest
from fractions import Fraction

from helpers import Decisions, FixedBits

from balance_trees import (
    BST,
    ConstantWalk,
    GeometricStop,
    HalvingWalk,
    InverseDepthWalk,
    TreeFlavor,
    ZigZag,
)
from balance_trees.strategies import STRATEGIES


def chain(size):
    tree = BST()
    for key in range(1, size + 1):
        tree.insert(key)
    return tree


class StrategyTests(unittest.TestCase):
    def test_halving_keeps_walking_after_every_failure(self):
        bits = Decisions([False] * 5)
        flavor = TreeFlavor(HalvingWalk(), tree=chain(5), bits=bits)
        stats = flavor.insert(6)
        self.assertEqual(bits.probabilities, [(1, 2**k) for k in range(1, 6)])
        self.assertEqual(stats.visits, 5)
        self.assertEqual(stats.rotations, 0)
        self.assertEqual(flavor.tree.depths()[6], 5)

    def test_halving_continues_at_new_parent_after_success(self):
        bits = Decisions([True] * 3)
        flavor = TreeFlavor(HalvingWalk(), tree=chain(5), bits=bits)
        stats = flavor.insert(6)
        self.assertEqual(bits.probabilities, [(1, 2), (1, 4), (1, 8)])
        self.assertEqual(stats.rotation_distances, [0, 2, 4])
        self.assertEqual(stats.visits, 3)
        self.assertEqual(flavor.tree.root.key, 2)
        self.assertEqual(flavor.tree.depths(), {2: 0, 1: 1, 4: 1, 3: 2, 6: 2, 5: 3})

    def test_halving_mixed_decisions_do_not_undo_previous_rotations(self):
        bits = Decisions([False, True, False, True])
        flavor = TreeFlavor(HalvingWalk(), tree=chain(6), bits=bits)
        stats = flavor.insert(7)
        self.assertEqual(stats.rotation_distances, [1, 4])
        self.assertEqual(stats.visits, 4)
        self.assertEqual(len(flavor.tree.depths()), 7)

    def test_halving_counts_actual_fair_bits(self):
        flavor = TreeFlavor(HalvingWalk(), tree=chain(5), bits=FixedBits([0] * 6))
        stats = flavor.insert(6)
        self.assertEqual(stats.rotations, 3)
        self.assertEqual(stats.random_bits, 6)

    def test_root_and_duplicates_consume_no_randomness(self):
        for strategy in (HalvingWalk(), ConstantWalk(), InverseDepthWalk()):
            with self.subTest(strategy=type(strategy).__name__):
                flavor = TreeFlavor(strategy, bits=FixedBits([]))
                first = flavor.insert(4)
                duplicate = flavor.insert(4)
                self.assertEqual(first.random_bits, 0)
                self.assertEqual(first.visits, 0)
                self.assertFalse(duplicate.inserted)
                self.assertEqual(duplicate.random_bits, 0)

    def test_constant_half_keeps_probability_and_continues_after_both_outcomes(self):
        bits = Decisions([False, True, False, True])
        flavor = TreeFlavor(ConstantWalk(), tree=chain(6), bits=bits)
        stats = flavor.insert(7)
        self.assertEqual(bits.probabilities, [(1, 2)] * 4)
        self.assertEqual(stats.rotation_distances, [1, 4])
        self.assertEqual(stats.visits, 4)
        self.assertEqual(len(flavor.tree.depths()), 7)

    def test_constant_half_uses_one_fair_bit_per_decision(self):
        flavor = TreeFlavor(ConstantWalk(), tree=chain(6), bits=FixedBits([1, 0, 1, 0]))
        stats = flavor.insert(7)
        self.assertEqual(stats.visits, 4)
        self.assertEqual(stats.rotations, 2)
        self.assertEqual(stats.random_bits, 4)

    def test_constant_probability_extremes_consume_no_random_bits(self):
        for probability, rotations, visits in [
            (Fraction(0), 0, 5),
            (Fraction(1), 3, 3),
        ]:
            flavor = TreeFlavor(
                ConstantWalk(probability), tree=chain(5), bits=FixedBits([])
            )
            stats = flavor.insert(6)
            self.assertEqual(stats.rotations, rotations)
            self.assertEqual(stats.visits, visits)
            self.assertEqual(stats.random_bits, 0)
            self.assertEqual(len(flavor.tree.depths()), 6)

    def test_constant_probability_rejects_values_outside_unit_interval(self):
        for probability in (Fraction(-1, 2), Fraction(3, 2)):
            with self.assertRaises(ValueError):
                ConstantWalk(probability)

    def test_inverse_depth_is_frozen_despite_rotations_and_ascent(self):
        bits = Decisions([False, True, False, True])
        flavor = TreeFlavor(InverseDepthWalk(), tree=chain(6), bits=bits)
        stats = flavor.insert(7)
        self.assertEqual(stats.insertion_depth, 6)
        self.assertEqual(bits.probabilities, [(1, 6)] * 4)
        self.assertEqual(stats.rotation_distances, [1, 4])
        self.assertEqual(stats.visits, 4)
        self.assertEqual(len(flavor.tree.depths()), 7)

    def test_inverse_depth_one_rotates_certainly_without_bits(self):
        flavor = TreeFlavor(InverseDepthWalk(), tree=chain(1), bits=FixedBits([]))
        stats = flavor.insert(2)
        self.assertEqual(stats.rotations, 1)
        self.assertEqual(stats.visits, 1)
        self.assertEqual(stats.random_bits, 0)
        self.assertEqual(flavor.tree.depths(), {2: 0, 1: 1})

    def test_inverse_depth_uses_fresh_depth_for_each_insertion(self):
        bits = Decisions([False] * 5)
        flavor = TreeFlavor(InverseDepthWalk(), tree=chain(2), bits=bits)
        flavor.insert(3)
        flavor.insert(4)
        self.assertEqual(bits.probabilities, [(1, 2)] * 2 + [(1, 3)] * 3)

    def test_inverse_depth_monotone_insertions_remain_a_chain_without_random_bits(self):
        for values in (range(64), range(63, -1, -1)):
            flavor = TreeFlavor(InverseDepthWalk(), bits=FixedBits([]))
            for index, key in enumerate(values):
                stats = flavor.insert(key)
                self.assertEqual(stats.insertion_depth, 0 if index == 0 else 1)
                self.assertEqual(stats.rotations, 0 if index == 0 else 1)
                self.assertEqual(stats.random_bits, 0)
                self.assertEqual(flavor.tree.root.key, key)
            depths = flavor.tree.depths()
            self.assertEqual(max(depths.values()), 63)
            self.assertEqual(sum(depths.values()) / len(depths), 31.5)

    def test_paper_zig_stops_after_first_rotation(self):
        flavor = TreeFlavor(GeometricStop(), tree=chain(5), bits=Decisions([False]))
        stats = flavor.insert(6)
        self.assertEqual(stats.visits, 1)
        self.assertEqual(stats.rotation_distances, [0])
        self.assertEqual(len(flavor.tree.depths()), 6)

    def test_paper_zigzag_uses_two_rotations_for_bent_path(self):
        tree = BST()
        tree.insert(3)
        tree.insert(1)
        flavor = TreeFlavor(
            GeometricStop(Fraction(3, 4), ZigZag()), tree=tree, bits=Decisions([False])
        )
        stats = flavor.insert(2)
        self.assertEqual(stats.rotations, 2)
        self.assertEqual(tree.depths(), {2: 0, 1: 1, 3: 1})

    def test_paper_zigzag_uses_one_rotation_for_straight_path(self):
        flavor = TreeFlavor(
            GeometricStop(Fraction(3, 4), ZigZag()),
            tree=chain(2),
            bits=Decisions([False]),
        )
        stats = flavor.insert(3)
        self.assertEqual(stats.rotation_distances, [1])
        self.assertEqual(flavor.tree.depths(), {2: 0, 1: 1, 3: 1})

    def test_paper_zigzag_does_nothing_without_two_ancestors(self):
        flavor = TreeFlavor(
            GeometricStop(Fraction(3, 4), ZigZag()),
            tree=chain(1),
            bits=Decisions([False]),
        )
        stats = flavor.insert(2)
        self.assertEqual(stats.rotations, 0)
        self.assertEqual(flavor.tree.depths(), {1: 0, 2: 1})

    def test_all_small_permutations_preserve_invariants_after_each_insertion(self):
        for name, factory in STRATEGIES.items():
            for seed in (0, 9):
                for values in itertools.permutations(range(1, 7)):
                    flavor = TreeFlavor(factory(), seed=seed)
                    inserted = set()
                    for key in values:
                        stats = flavor.insert(key)
                        inserted.add(key)
                        self.assertEqual(set(flavor.tree.depths()), inserted)
                        if name == "paper-zig":
                            self.assertLessEqual(stats.rotations, 1)
                        elif name == "paper-zigzag":
                            self.assertLessEqual(stats.rotations, 2)
                        elif name in {"halving", "constant-half", "inverse-depth"}:
                            self.assertLessEqual(stats.visits, stats.insertion_depth)
                            self.assertGreaterEqual(
                                stats.visits, stats.insertion_depth - stats.rotations
                            )
