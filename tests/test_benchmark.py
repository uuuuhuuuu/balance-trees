import json
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from balance_trees.benchmark import run_benchmarks
from balance_trees.benchmark_report import generate_report


class BenchmarkTests(unittest.TestCase):
    def test_real_trials_validate_trees_and_generate_portable_reports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            results = run_benchmarks(
                root / "run",
                sizes=[8, 16],
                trials=2,
                seed=2026,
                strategies=["none", "random-level"],
                orders=["increasing"],
                timeout=5,
            )
            self.assertEqual(len(results["trials"]), 8)
            plain = next(
                row
                for row in results["summaries"]
                if row["strategy"] == "none" and row["n"] == 8
            )
            self.assertEqual(plain["mean_depth"], 3.5)
            self.assertEqual(plain["height"], 7)
            self.assertEqual(plain["mean_rotations"], 0)
            self.assertGreater(plain["seconds"], 0)
            self.assertEqual(plain["completed_trials"], 2)
            self.assertEqual(plain["mean_depth_se"], 0)
            generate_report(root / "run", root / "site")
            for name in ("summary.html", "results.html"):
                text = (root / "site" / name).read_text()
                self.assertIn("random-level", text)
                self.assertIn("./results/trials.csv", text)
                self.assertNotIn("https://", text)
            for svg in (root / "site" / "results").glob("*.svg"):
                self.assertEqual(
                    ET.parse(svg).getroot().tag, "{http://www.w3.org/2000/svg}svg"
                )
            self.assertEqual(
                json.loads((root / "site/results/results.json").read_text()), results
            )

    def test_timeout_is_censored_and_remaining_trials_are_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch(
                "balance_trees.benchmark.subprocess.run",
                side_effect=subprocess.TimeoutExpired("worker", 0.01),
            ) as spawn:
                results = run_benchmarks(
                    root / "run",
                    sizes=[100],
                    trials=3,
                    seed=42,
                    strategies=["none"],
                    orders=["increasing"],
                    timeout=0.01,
                )
            self.assertEqual(spawn.call_count, 1)
            self.assertEqual(
                [r["status"] for r in results["trials"]],
                ["timeout", "not_run", "not_run"],
            )
            summary = results["summaries"][0]
            self.assertNotIn("seconds", summary)
            self.assertNotIn("mean_depth", summary)
            generate_report(root / "run", root / "site")
            svg = (root / "site/results/increasing-mean_depth.svg").read_text()
            self.assertNotIn('<circle cx="67.00" cy=', svg)
            self.assertIn("timeout", (root / "site/summary.html").read_text())

    def test_fresh_output_and_input_validation_preserve_previous_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "keep.txt"
            marker.write_text("original")
            options = dict(
                sizes=[8],
                trials=1,
                seed=0,
                strategies=["none"],
                orders=["random"],
                timeout=1,
            )
            with self.assertRaises(FileExistsError):
                run_benchmarks(root, **options)
            with self.assertRaises(ValueError):
                run_benchmarks(root / "bad", **{**options, "sizes": [8, 8]})
            self.assertEqual(marker.read_text(), "original")
