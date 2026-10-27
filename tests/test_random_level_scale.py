import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux resource limits")
class RandomLevelScaleTests(unittest.TestCase):
    def test_sweep_validates_every_workload_and_records_memory(self):
        script = Path(__file__).resolve().parents[1] / "benchmarks/random_level_scale.py"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--min-power",
                    "2",
                    "--max-power",
                    "3",
                    "--memory-mib",
                    "256",
                    "--output",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            results = json.loads((output / "results.json").read_text())
            self.assertEqual(results["metadata"]["sizes"], [4, 8])
            self.assertEqual(len(results["trials"]), 14)
            self.assertTrue(all(r["status"] == "complete" for r in results["trials"]))
            self.assertTrue(
                all(r["metrics"]["mean_random_bits"] == 64 for r in results["trials"])
            )
            memory = json.loads((output / "memory.json").read_text())
            self.assertLessEqual(memory["address_space_limit_bytes"], 256 * 1024**2)
            self.assertGreater(memory["peak_child_rss_bytes"], 0)

    def test_oversized_inputs_fail_with_recorded_memory_errors(self):
        script = Path(__file__).resolve().parents[1] / "benchmarks/random_level_scale.py"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            process = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--min-power",
                    "30",
                    "--max-power",
                    "30",
                    "--memory-mib",
                    "64",
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(process.returncode, 0)
            results = json.loads((output / "results.json").read_text())
            self.assertEqual(len(results["trials"]), 7)
            for trial in results["trials"]:
                self.assertEqual(trial["status"], "error")
                self.assertIn("MemoryError", trial["detail"])
            self.assertTrue((output / "memory.json").exists())
