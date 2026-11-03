"""Compare the depth of each inserted vertex before balancing.

The default comparison uses the Treap-style ``random-level`` strategy for both
sides so the test runs with the strategies currently registered in the
repository. Set ``V21_STRATEGY`` once the v2.1 implementation is registered.
"""

import csv
import os
import unittest
from pathlib import Path

import matplotlib.pyplot as plt

from balance_trees import TreeFlavor
from balance_trees.sequences import insertion_order
from balance_trees.strategies import STRATEGIES, create_strategy

TREAP_STRATEGY = os.environ.get("TREAP_STRATEGY", "random-level")
V21_STRATEGY = os.environ.get("V21_STRATEGY", "random-level")
N = int(os.environ.get("INSERTION_COUNT", "2000"))
SEED = int(os.environ.get("EXPERIMENT_SEED", "2026"))
OUTPUT = Path(
    os.environ.get(
        "INSERTION_DEPTH_OUTPUT",
        "benchmarks/results/insertion-depth-comparison",
    )
)


class InsertionDepthGraphTests(unittest.TestCase):
    def test_records_pre_balancing_insertion_depths(self):
        for name in (TREAP_STRATEGY, V21_STRATEGY):
            self.assertIn(name, STRATEGIES)

        keys = insertion_order("random", N, SEED)
        series = {}

        for name in (TREAP_STRATEGY, V21_STRATEGY):
            flavor = TreeFlavor(create_strategy(name), seed=SEED)
            depths = []
            for key in keys:
                stats = flavor.insert(key)
                self.assertTrue(stats.inserted)
                depths.append(stats.insertion_depth)
            series[name] = depths
            self.assertEqual(set(flavor.tree.depths()), set(keys))

        OUTPUT.mkdir(parents=True, exist_ok=True)
        csv_path = OUTPUT / "insertion_depths.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["insertion_index", "key", TREAP_STRATEGY, V21_STRATEGY])
            for index, key in enumerate(keys):
                writer.writerow(
                    [
                        index,
                        key,
                        series[TREAP_STRATEGY][index],
                        series[V21_STRATEGY][index],
                    ]
                )

        fig, ax = plt.subplots(figsize=(12, 5))
        for name, depths in series.items():
            ax.plot(range(len(depths)), depths, label=name, linewidth=0.8)
        ax.set_title("Depth of inserted vertex before balancing")
        ax.set_xlabel("Insertion index")
        ax.set_ylabel("Insertion depth (edges; root = 0)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        graph_path = OUTPUT / "insertion_depths.png"
        fig.savefig(graph_path, dpi=160)
        plt.close(fig)

        self.assertTrue(csv_path.is_file())
        self.assertTrue(graph_path.is_file())


if __name__ == "__main__":
    unittest.main()
