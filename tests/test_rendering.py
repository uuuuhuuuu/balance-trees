import unittest

from balance_trees import BST, render_tree


class RenderingTests(unittest.TestCase):
    def test_empty_tree(self):
        self.assertEqual(render_tree(BST()), "<empty>")

    def test_left_and_right_branches_are_unambiguous(self):
        tree = BST()
        for key in [4, 2, 6, 3, 5]:
            tree.insert(key)
        self.assertEqual(
            render_tree(tree), "4\n├── L: 2\n│   └── R: 3\n└── R: 6\n    └── L: 5"
        )
        self.assertEqual(str(tree), render_tree(tree))

    def test_ascii_output_and_depth_limit(self):
        tree = BST()
        for key in range(4):
            tree.insert(key)
        self.assertEqual(
            render_tree(tree, max_depth=0, ascii_only=True), "0\n`-- ... (depth limit)"
        )
        diagram = render_tree(tree, max_depth=1, ascii_only=True)
        self.assertTrue(diagram.isascii())
        self.assertIn("R: 1", diagram)
        self.assertNotIn("R: 2", diagram)

    def test_node_limit_is_explicit(self):
        tree = BST()
        for key in [4, 2, 6]:
            tree.insert(key)
        self.assertEqual(render_tree(tree, max_nodes=1), "4\n├── … (node limit)")

    def test_invalid_limits(self):
        for options in ({"max_nodes": 0}, {"max_depth": -1}):
            with self.assertRaises(ValueError):
                render_tree(BST(), **options)
