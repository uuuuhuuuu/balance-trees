import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from balance_trees import TreeFlavor
from balance_trees.showcase import build_trace, parse_sequence
from balance_trees.showcase.server import ShowcaseHandler
from balance_trees.strategies import STRATEGIES


class ShowcaseTraceTests(unittest.TestCase):
    def test_csv_supports_whitespace_negative_keys_zero_and_duplicates(self):
        self.assertEqual(parse_sequence(" 8, -4,\n0, +12, 8 "), [8, -4, 0, 12, 8])

    def test_csv_rejects_empty_fields_nonintegers_and_oversized_sequences(self):
        for text in (
            "",
            "1,,2",
            "1,",
            "1 2",
            "1.5,2",
            "NaN",
            "9007199254740992",
            ",".join(["1"] * 129),
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_sequence(text)

    def test_actual_python_flavors_match_normal_execution_without_extra_randomness(
        self,
    ):
        values = [8, 4, 12, 2, 6, 10, 14, 5, 0, -1, 8]
        for name, factory in STRATEGIES.items():
            with self.subTest(strategy=name):
                trace = build_trace(values, name, 2026)
                flavor = TreeFlavor(factory(), seed=2026)
                rotations = visits = scans = 0
                for key in values:
                    stats = flavor.insert(key)
                    rotations += stats.rotations
                    visits += stats.visits
                    scans += stats.scanned_nodes
                final = trace["frames"][-1]
                actual = {}
                for node in final["nodes"]:
                    actual[node["key"]] = (node["left"], node["right"])
                expected = {}
                stack = [flavor.tree.root]
                while stack:
                    node = stack.pop()
                    expected[node.key] = (
                        node.left.key if node.left else None,
                        node.right.key if node.right else None,
                    )
                    stack.extend(child for child in (node.left, node.right) if child)
                self.assertEqual(actual, expected)
                self.assertEqual(final["stats"]["rotations"], rotations)
                self.assertEqual(final["stats"]["visits"], visits)
                self.assertEqual(final["stats"]["scanned_nodes"], scans)
                self.assertEqual(
                    sum(frame["kind"] == "scan" for frame in trace["frames"]), scans
                )
                self.assertEqual(final["stats"]["random_bits"], flavor.bits.count)
                self.assertEqual(
                    sum(frame["kind"] == "rotate" for frame in trace["frames"]),
                    rotations,
                )
                self.assertEqual(
                    sum(
                        frame["kind"] in {"priority", "coin", "visit"}
                        for frame in trace["frames"]
                    ),
                    visits,
                )

    def test_each_treap_insertion_finishes_with_valid_heap_order(self):
        values = [1, 12, 2, 11, 3, 10, 4, 9, 5, 8, 6, 7]
        trace = build_trace(values, "treap", 2026)
        settled = [frame for frame in trace["frames"] if frame["kind"] == "settled"]
        self.assertEqual(len(settled), len(values))
        for index, frame in enumerate(settled):
            self.assertTrue(frame["heap_valid"])
            self.assertEqual(frame["stats"]["nodes"], index + 1)
        self.assertEqual(set(node["key"] for node in settled[-1]["nodes"]), set(values))
        self.assertEqual(settled[-1]["stats"]["random_bits"], 32 * len(values))
        nodes = settled[-1]["nodes"]
        self.assertEqual(
            settled[-1]["root"],
            min(nodes, key=lambda node: (node["priority"], node["key"]))["key"],
        )

    def test_each_rotation_has_before_after_snapshots_and_increments_once(self):
        trace = build_trace(list(range(1, 17)), "treap", 9)
        pairs = 0
        for before, after in zip(trace["frames"], trace["frames"][1:]):
            if before["kind"] == "prepare":
                pairs += 1
                self.assertEqual(after["kind"], "rotate")
                self.assertEqual(before["promoted"], after["promoted"])
                self.assertEqual(
                    before["stats"]["rotations"] + 1, after["stats"]["rotations"]
                )
                self.assertEqual(
                    {node["key"] for node in before["nodes"]},
                    {node["key"] for node in after["nodes"]},
                )
        self.assertGreater(pairs, 0)

    def test_duplicates_do_not_generate_priority_or_coin_bits(self):
        for strategy in ["treap", *STRATEGIES]:
            trace = build_trace([4, 2, 4], strategy)
            settled = [frame for frame in trace["frames"] if frame["kind"] == "settled"]
            self.assertEqual(
                settled[1]["stats"]["random_bits"], settled[2]["stats"]["random_bits"]
            )
            self.assertEqual(settled[2]["stats"]["nodes"], 2)
            self.assertEqual(settled[2]["stats"]["insertion_rotations"], 0)

    def test_trace_is_deterministic_and_json_serializable(self):
        left = build_trace([4, 2, 6, 1, 3], "treap", 42)
        right = build_trace([4, 2, 6, 1, 3], "treap", 42)
        self.assertEqual(json.dumps(left), json.dumps(right))
        self.assertEqual(left["schema_version"], 1)

    def test_invalid_trace_parameters(self):
        cases = [
            ([], "treap", 0),
            ([True], "treap", 0),
            ([1.5], "treap", 0),
            ([1], "unknown", 0),
            ([1], "treap", -1),
            ([1], "treap", 2**32),
        ]
        for values, strategy, seed in cases:
            with self.assertRaises(ValueError):
                build_trace(values, strategy, seed)

    def test_trace_export_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "trace.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "balance_trees.showcase",
                    "--strategy",
                    "halving",
                    "--sequence",
                    "8,4,12,2",
                    "--export",
                    str(destination),
                ],
                check=True,
                capture_output=True,
            )
            trace = json.loads(destination.read_text())
            self.assertEqual(trace["source"], "python")
            self.assertEqual(trace["strategy"], "halving")
            self.assertEqual(trace["sequence"], [8, 4, 12, 2])

    def test_trace_api_validates_without_requiring_a_listening_socket(self):
        def request(payload):
            body = json.dumps(payload).encode()
            handler = ShowcaseHandler.__new__(ShowcaseHandler)
            handler.path = "/api/trace"
            handler.headers = {"Content-Length": str(len(body))}
            handler.rfile = io.BytesIO(body)
            responses = []
            handler.respond = lambda status, response: responses.append(
                (status, response)
            )
            handler.do_POST()
            return responses[0]

        status, response = request(
            {"sequence": [1, 2, 3], "strategy": "treap", "seed": 42}
        )
        self.assertEqual(status, 200)
        self.assertEqual(response["source"], "python")
        status, response = request({"sequence": [1, "bad"]})
        self.assertEqual(status, 400)
        self.assertIn("error", response)
