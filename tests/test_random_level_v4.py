"""Dispatch and shared-history checks for the v4 hybrid."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from balance_trees.strategies import RandomLevelV4, create_strategy
from balance_trees.strategies.random_level_v2 import RandomLevelV2
from balance_trees.strategies.random_level_v3 import RandomLevelV3


class RandomLevelV4Tests(unittest.TestCase):
    def test_factory(self):
        self.assertIsInstance(create_strategy("random-level-v4"), RandomLevelV4)

    def test_dispatch(self):
        for count, depth, expected in [(0, 0, 3), (1, 1, 3), (200, 5, 2), (200, 6, 3)]:
            with self.subTest(count=count, depth=depth):
                policy = RandomLevelV4(inserted_count=count)
                context = SimpleNamespace(stats=SimpleNamespace(insertion_depth=depth))
                with patch.object(RandomLevelV2, "rebalance", autospec=True) as v2:
                    with patch.object(RandomLevelV3, "rebalance", autospec=True) as v3:
                        policy.rebalance(context)
                        selected, other = (v2, v3) if expected == 2 else (v3, v2)
                        selected.assert_called_once_with(policy, context)
                        other.assert_not_called()

    def test_equality_uses_v3(self):
        policy = RandomLevelV4(inserted_count=10)
        context = SimpleNamespace(stats=SimpleNamespace(insertion_depth=2))
        with patch("balance_trees.strategies.random_level_v4.math.log", return_value=2):
            with patch.object(RandomLevelV3, "rebalance", autospec=True) as v3:
                policy.rebalance(context)
                v3.assert_called_once_with(policy, context)

    def test_shared_history_across_switch(self):
        policy = RandomLevelV4(inserted_count=200, lowest_priority=10, highest_priority=100)
        context = SimpleNamespace(stats=SimpleNamespace(insertion_depth=5))

        def v2_step(state, ctx):
            self.assertIs(state, policy)
            state.inserted_count += 1
            state.lowest_priority = 5
            state.highest_priority = 120

        def v3_step(state, ctx):
            self.assertIs(state, policy)
            self.assertEqual((state.inserted_count, state.lowest_priority, state.highest_priority), (201, 5, 120))
            state.inserted_count += 1

        with patch.object(RandomLevelV2, "rebalance", autospec=True, side_effect=v2_step):
            with patch.object(RandomLevelV3, "rebalance", autospec=True, side_effect=v3_step):
                policy.rebalance(context)
                context.stats.insertion_depth = 6
                policy.rebalance(context)
        self.assertEqual(policy.inserted_count, 202)


if __name__ == "__main__":
    unittest.main()
