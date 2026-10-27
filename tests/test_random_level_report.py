import csv
import json
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from balance_trees.random_level_report import comparison_results, generate_v2_report
from balance_trees.showcase.server import STATIC

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "benchmarks/random-level-v2"
BASELINE = STATIC / "random-level-results/results.json"
DESCRIPTION = ROOT / "docs/random-level-v2.md"


class RandomLevelReportTests(unittest.TestCase):
    def test_report_preserves_historical_data_and_links_the_new_page(self):
        source_bytes = {p.name: p.read_bytes() for p in SOURCE.iterdir()}
        baseline_bytes = BASELINE.read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            original = '<nav><a href="./summary.html">Existing report</a></nav><p>Preserved results.</p>'
            (output / "results.html").write_text(original)
            generate_v2_report(SOURCE, BASELINE, DESCRIPTION, output)
            html = (output / "random-level-v2.html").read_text()
            self.assertIn("What changes in v2", html)
            self.assertIn("Why expected rotations are below three", html)
            self.assertIn("not guarantee logarithmic depth", html)
            self.assertIn("no cross-version timing comparison", html)
            self.assertEqual(html.count("data-workload="), 7)
            self.assertEqual(html.count('<figure class="chart">'), 28)
            self.assertIn("./random-level-v2-results/description.md", html)
            self.assertIn("./random-level-v2-results/paired-summary.csv", html)
            self.assertIn("Preserved results.", (output / "results.html").read_text())
            self.assertIn(
                "./random-level-v2.html", (output / "results.html").read_text()
            )
            results = json.loads(
                (output / "random-level-v2-results/results.json").read_text()
            )
            self.assertEqual(len(results["trials"]), 126)
            self.assertEqual(len(results["summaries"]), 42)
            paired = [
                r
                for r in results["summaries"]
                if r["order"] == "random" and r["n"] == 128000
            ]
            self.assertAlmostEqual(paired[0]["mean_rotations"], 7.0900859375)
            self.assertAlmostEqual(paired[1]["mean_rotations"], 1.2596901041666666)
            ns = {"s": "http://www.w3.org/2000/svg"}
            for svg in (output / "random-level-v2-results").glob("*.svg"):
                root = ET.parse(svg).getroot()
                self.assertIsNotNone(root.find('s:path[@class="log-reference"]', ns))
            # A second generation is idempotent and does not duplicate navigation.
            generate_v2_report(SOURCE, BASELINE, DESCRIPTION, output)
            self.assertEqual(
                (output / "results.html").read_text().count("./random-level-v2.html"), 1
            )
        self.assertEqual(BASELINE.read_bytes(), baseline_bytes)
        self.assertEqual(
            {p.name: p.read_bytes() for p in SOURCE.iterdir()}, source_bytes
        )

    def test_changed_baseline_and_unpaired_seeds_fail_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            changed = root / "baseline.json"
            changed.write_text("{}")
            with self.assertRaisesRegex(ValueError, "checksum"):
                generate_v2_report(SOURCE, changed, DESCRIPTION, root / "site")
            self.assertFalse((root / "site").exists())
            source = root / "input"
            shutil.copytree(SOURCE, source)
            with (source / "trials.csv").open(newline="") as handle:
                reader = csv.DictReader(handle)
                columns, rows = reader.fieldnames, list(reader)
            rows[0]["seed"] = "1"
            with (source / "trials.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, columns)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "matching baseline"):
                generate_v2_report(source, BASELINE, DESCRIPTION, root / "site")
            self.assertFalse((root / "site").exists())

    def test_comparison_uses_exact_pairing_and_keeps_baseline_records_intact(self):
        results = comparison_results(SOURCE, BASELINE)
        original = json.loads(BASELINE.read_text())
        indexed = {
            (r["n"], r["order"], r["trial"], r["seed"], r["order_seed"]): r
            for r in original["trials"]
        }
        for old, new in zip(results["trials"][:63], results["trials"][63:]):
            key = (new["n"], new["order"], new["trial"], new["seed"], new["order_seed"])
            self.assertEqual(old, indexed[key])
