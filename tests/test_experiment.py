import csv
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from balance_trees.experiment import run_experiment
from balance_trees.measurement import run_trial
from balance_trees.sequences import ORDERS, insertion_order
from balance_trees.statistics import TrialAggregate, standard_error
from balance_trees.strategies import STRATEGIES, NoRebalance


class ExperimentTests(unittest.TestCase):
    def test_orders_are_permutations_for_even_and_odd_sizes(self):
        for name in ORDERS:
            for n in (1, 2, 5, 6):
                self.assertEqual(
                    sorted(insertion_order(name, n, 42)), list(range(1, n + 1))
                )
        self.assertEqual(insertion_order("converging", 6, 0), [1, 6, 2, 5, 3, 4])
        self.assertEqual(insertion_order("pairs", 6, 0), [2, 1, 4, 3, 6, 5])
        self.assertEqual(insertion_order("bitonic", 6, 0), [2, 4, 6, 5, 3, 1])
        self.assertEqual(insertion_order("runs", 6, 0), [2, 4, 6, 1, 3, 5])

    def test_plain_sorted_tree_matches_exact_depth_and_work(self):
        result = run_trial(list(range(1, 11)), NoRebalance(), 0)
        self.assertEqual(result.metrics.mean_depth, 4.5)
        self.assertEqual(result.metrics.height, 9)
        self.assertEqual(result.metrics.mean_insertion_depth, 4.5)
        self.assertEqual(result.metrics.mean_rotations, 0)
        self.assertEqual(result.metrics.mean_visits, 0)
        self.assertEqual(result.metrics.mean_random_bits, 0)

    def test_per_key_expectation_is_distinct_from_expected_height(self):
        aggregate = TrialAggregate(3)
        aggregate.add(run_trial([1, 2, 3], NoRebalance(), 0))
        aggregate.add(run_trial([3, 2, 1], NoRebalance(), 0))
        summary = aggregate.summary()
        self.assertEqual(summary["worst_key_mean_depth"], 1)
        self.assertEqual(summary["mean_height"], 2)
        self.assertEqual(summary["mean_depth_se"], 0)
        nodes = list(aggregate.node_rows())
        self.assertEqual([row["mean_depth"] for row in nodes], [1, 1, 1])
        self.assertEqual([row["depth_se"] for row in nodes], [1, 0, 1])
        self.assertIsNone(summary["rotations_within_2_edges_fraction"])
        self.assertEqual(list(aggregate.distance_rows()), [])

    def test_standard_error_uses_independent_trials(self):
        self.assertIsNone(standard_error([2]))
        self.assertAlmostEqual(standard_error([1, 3, 5]), 2 / math.sqrt(3))

    def test_exports_are_reproducible_and_include_per_key_statistics(self):
        with tempfile.TemporaryDirectory() as temporary:
            left, right = Path(temporary) / "left", Path(temporary) / "right"
            for destination in (left, right):
                report = run_experiment(
                    destination,
                    [8, 16],
                    3,
                    2026,
                    list(STRATEGIES),
                    list(ORDERS),
                    check_every_insertion=True,
                )
                self.assertIn("Depth +/- SE", report)
                self.assertIn("Theta(insertion depth)", report)
            self.assertEqual(
                {path.name for path in left.iterdir()},
                {
                    "config.json",
                    "trials.csv",
                    "summary.csv",
                    "node_depths.csv",
                    "rotation_distances.csv",
                    "report.txt",
                    "report.md",
                },
            )
            for path in left.iterdir():
                self.assertEqual(path.read_bytes(), (right / path.name).read_bytes())
            with (left / "summary.csv").open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2 * len(STRATEGIES) * len(ORDERS))
            with (left / "node_depths.csv").open() as handle:
                self.assertEqual(
                    sum(1 for _ in csv.DictReader(handle)),
                    (8 + 16) * len(STRATEGIES) * len(ORDERS),
                )
            metadata = json.loads((left / "config.json").read_text())
            self.assertEqual(metadata["trials"], 3)
            self.assertIn("decisions", metadata["halving_probability"])
            with (left / "rotation_distances.csv").open() as handle:
                distance_rows = list(csv.DictReader(handle))
            groups = {}
            for row in distance_rows:
                groups.setdefault((row["strategy"], row["order"], row["n"]), []).append(
                    row
                )
            for group in groups.values():
                self.assertAlmostEqual(sum(float(row["fraction"]) for row in group), 1)
                self.assertEqual(float(group[-1]["cumulative_fraction"]), 1)

    def test_existing_results_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            marker = path / "keep.txt"
            marker.write_text("original")
            with self.assertRaises(FileExistsError):
                run_experiment(path, [8], 1, 0, ["halving"], ["increasing"])
            self.assertEqual(marker.read_text(), "original")
            self.assertEqual(list(path.iterdir()), [marker])

    def test_one_trial_reports_unknown_standard_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "results"
            report = run_experiment(output, [2], 1, 0, ["halving"], ["increasing"])
            self.assertIn("SE n/a", report)
            with (output / "summary.csv").open() as handle:
                self.assertEqual(next(csv.DictReader(handle))["mean_depth_se"], "")

    def test_invalid_experiment_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "results"
            with self.assertRaises(ValueError):
                run_experiment(output, [1], 1, 0, ["halving"], ["increasing"])
            self.assertFalse(output.exists())

    def test_demo_cli_prints_readable_tree_and_metrics(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "balance_trees.demo",
                "--keys",
                "4",
                "2",
                "6",
                "--trace",
                "--ascii",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("Final tree:", result.stdout)
        self.assertIn("Rotations", result.stdout)
        self.assertIn("Nodes: 3", result.stdout)
        self.assertTrue(result.stdout.isascii())
