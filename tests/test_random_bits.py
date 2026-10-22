import itertools
import unittest

from helpers import FixedBits

from balance_trees.random_bits import RandomBits


class RandomBitTests(unittest.TestCase):
    def test_dyadic_probabilities_are_exact_over_all_bit_strings(self):
        for width in range(1, 6):
            denominator = 2**width
            for numerator in range(denominator + 1):
                successes = 0
                for values in itertools.product((0, 1), repeat=width):
                    source = FixedBits(values)
                    successes += source.bernoulli(numerator, denominator)
                    self.assertLessEqual(source.count, width)
                self.assertEqual(successes, numerator)

    def test_deterministic_probabilities_consume_no_bits(self):
        source = FixedBits([])
        self.assertFalse(source.bernoulli(0, 7))
        self.assertTrue(source.bernoulli(7, 7))
        self.assertEqual(source.count, 0)

    def test_non_dyadic_coin_and_expected_bit_cost(self):
        source = RandomBits(2026)
        trials = 30000
        successes = sum(source.bernoulli(1, 3) for _ in range(trials))
        self.assertAlmostEqual(successes / trials, 1 / 3, delta=0.01)
        self.assertLess(source.count / trials, 2.05)

    def test_tiny_probability_does_not_underflow(self):
        source = FixedBits([0] * 1200)
        self.assertTrue(source.bernoulli(1, 2**1200))
        self.assertEqual(source.count, 1200)

    def test_invalid_probabilities(self):
        source = RandomBits(0)
        for probability in [(-1, 2), (3, 2), (1, 0)]:
            with self.assertRaises(ValueError):
                source.bernoulli(*probability)

    def test_seed_reproduces_bits_and_decisions(self):
        left, right = RandomBits(42), RandomBits(42)
        self.assertEqual(
            [left.bernoulli(1, 7) for _ in range(100)],
            [right.bernoulli(1, 7) for _ in range(100)],
        )
        self.assertEqual(left.count, right.count)
