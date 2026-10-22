import json
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from balance_trees import BST, render_graphviz, to_dot, write_dot


def example_tree():
    tree = BST()
    for key in [4, 2, 6, 3, 5]:
        tree.insert(key)
    return tree


class DotExportTests(unittest.TestCase):
    def test_export_records_keys_and_left_right_edges_without_mutation(self):
        tree = example_tree()
        before = tree.depths()
        source = to_dot(tree, highlight_key=3)
        self.assertIn('n0 [label="4"', source)
        self.assertIn('n0 -> n1 [label="L"]', source)
        self.assertIn('n0 -> n2 [label="R"]', source)
        self.assertIn('n1 -> n3 [label="R"]', source)
        self.assertIn('n2 -> n4 [label="L"]', source)
        self.assertIn('n3 [label="3", fillcolor="#fde68a"', source)
        self.assertEqual(tree.depths(), before)
        self.assertEqual(source, to_dot(example_tree(), highlight_key=3))

    def test_nulls_are_invisible_for_layout_or_explicit_on_request(self):
        tree = example_tree()
        hidden = to_dot(tree)
        self.assertIn('null_1_L [label="", shape=point, style=invis]', hidden)
        self.assertNotIn("null_3_L", hidden)
        explicit = to_dot(tree, show_nulls=True)
        self.assertIn('null_1_L [label="∅"', explicit)
        self.assertIn('null_3_L [label="∅"', explicit)
        self.assertEqual(explicit.count('label="∅"'), 6)
        self.assertNotIn("style=invis", explicit)

    def test_empty_tree_and_escaped_title(self):
        title = 'Tree "example" \\N\nnext line'
        source = to_dot(BST(), title=title)
        self.assertIn('empty [label="<empty>"', source)
        self.assertIn(f"label={json.dumps(title)}", source)

    def test_dot_export_works_without_graphviz(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "nested" / "tree.dot"
            with patch("balance_trees.graphviz.shutil.which", return_value=None):
                self.assertEqual(write_dot(example_tree(), path), path)
            self.assertEqual(path.read_text(), to_dot(example_tree()))

    def test_missing_renderer_has_actionable_error(self):
        with patch("balance_trees.graphviz.shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "export DOT"):
                render_graphviz(example_tree(), "unused.svg")

    def test_unsupported_render_format_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "suffix"):
            render_graphviz(example_tree(), "unused.html")

    def test_failed_render_preserves_existing_file(self):
        error = subprocess.CalledProcessError(1, ["dot"], stderr=b"render failure")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "tree.svg"
            path.write_text("original")
            with (
                patch("balance_trees.graphviz.shutil.which", return_value="dot"),
                patch("balance_trees.graphviz.subprocess.run", side_effect=error),
                self.assertRaisesRegex(RuntimeError, "render failure"),
            ):
                render_graphviz(example_tree(), path)
            self.assertEqual(path.read_text(), "original")


@unittest.skipUnless(shutil.which("dot"), "Graphviz dot is not installed")
class GraphvizIntegrationTests(unittest.TestCase):
    def test_svg_png_and_pdf_are_valid_rendered_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            for suffix, signature in [
                ("svg", b"<?xml"),
                ("png", b"\x89PNG\r\n\x1a\n"),
                ("pdf", b"%PDF-"),
            ]:
                with self.subTest(format=suffix):
                    path = Path(temporary) / f"tree.{suffix}"
                    render_graphviz(example_tree(), path, show_nulls=True)
                    self.assertTrue(path.read_bytes().startswith(signature))
                    self.assertGreater(path.stat().st_size, 100)
                    if suffix == "svg":
                        root = ET.parse(path).getroot()
                        text = " ".join(root.itertext())
                        for key in (4, 2, 6, 3, 5):
                            self.assertIn(str(key), text)

    def test_layout_preserves_single_child_left_and_right_positions(self):
        for child, relation in [(1, "left"), (3, "right")]:
            tree = BST()
            tree.insert(2)
            tree.insert(child)
            result = subprocess.run(
                [shutil.which("dot"), "-Tplain"],
                input=to_dot(tree),
                text=True,
                capture_output=True,
                check=True,
                timeout=10,
            )
            positions = {}
            for line in result.stdout.splitlines():
                parts = line.split()
                if parts[0] == "node" and parts[1] in {"n0", "n1"}:
                    positions[parts[1]] = float(parts[2])
            if relation == "left":
                self.assertLess(positions["n1"], positions["n0"])
            else:
                self.assertGreater(positions["n1"], positions["n0"])

    def test_escaped_title_is_accepted_by_graphviz(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "empty.svg"
            render_graphviz(BST(), path, title='Tree "quoted" \\N\nline two')
            root = ET.parse(path).getroot()
            text = " ".join(root.itertext())
            self.assertIn('Tree "quoted" \\N', text)
            self.assertIn("line two", text)
