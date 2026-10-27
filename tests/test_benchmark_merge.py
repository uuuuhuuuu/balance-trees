import copy
import json
import tempfile
import unittest
from pathlib import Path

from balance_trees.benchmark_merge import merge_runs
from balance_trees.showcase.server import STATIC


class BenchmarkMergeTests(unittest.TestCase):
    def setUp(self):
        self.recorded = json.loads(
            (STATIC / "random-level-results/results.json").read_text()
        )

    def write_run(self, root, name, sizes):
        run = copy.deepcopy(self.recorded)
        run["metadata"].pop("batches", None)
        run["metadata"]["sizes"] = sizes
        run["trials"] = [row for row in run["trials"] if row["n"] in sizes]
        source = root / name
        source.mkdir()
        (source / "results.json").write_text(json.dumps(run))
        return source, run

    def test_disjoint_runs_preserve_trials_summaries_and_batch_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, old = self.write_run(root, "first", [1000])
            second, new = self.write_run(root, "second", [2000])
            combined = merge_runs([first, second], root / "merged")
            self.assertEqual(combined["trials"], old["trials"] + new["trials"])
            self.assertEqual(combined["metadata"]["sizes"], [1000, 2000])
            self.assertEqual(
                combined["metadata"]["batches"], [old["metadata"], new["metadata"]]
            )
            expected = [
                row for row in self.recorded["summaries"] if row["n"] in (1000, 2000)
            ]
            self.assertEqual(combined["summaries"], expected)
            self.assertEqual(json.loads((first / "results.json").read_text()), old)
            for filename in (
                "config.json",
                "trials.jsonl",
                "summary.csv",
                "trials.csv",
            ):
                self.assertTrue((root / "merged" / filename).is_file())
            with self.assertRaises(FileExistsError):
                merge_runs([first, second], root / "merged")

    def test_overlapping_sizes_and_incompatible_settings_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, _ = self.write_run(root, "first", [1000])
            second, changed = self.write_run(root, "second", [2000])
            with self.assertRaisesRegex(ValueError, "disjoint"):
                merge_runs([first, first], root / "overlap")
            changed["metadata"]["seed"] += 1
            (second / "results.json").write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "same machine"):
                merge_runs([first, second], root / "mismatch")
            self.assertFalse((root / "overlap").exists())
            self.assertFalse((root / "mismatch").exists())
