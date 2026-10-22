import unittest

from balance_trees import BST, Node, TreeFlavor
from balance_trees.rotations import rotate_left, rotate_right, rotate_up


def structure(tree):
    def key(node):
        return node.key if node is not None else None

    nodes = [tree.root] if tree.root is not None else []
    result = {}
    while nodes:
        node = nodes.pop()
        result[node.key] = (key(node.parent), key(node.left), key(node.right))
        nodes.extend(child for child in (node.left, node.right) if child is not None)
    return result


class TreeTests(unittest.TestCase):
    def test_empty_and_duplicate_insertions(self):
        tree = BST()
        self.assertEqual(tree.depths(), {})
        self.assertFalse(tree.contains(7))
        first = tree.insert(7)
        duplicate = tree.insert(7)
        self.assertTrue(first.inserted)
        self.assertFalse(duplicate.inserted)
        self.assertIs(first.node, duplicate.node)
        self.assertEqual(tree.depths(), {7: 0})
        self.assertTrue(tree.contains(7))

    def test_nodes_store_only_elements_and_tree_structure(self):
        self.assertEqual(set(Node.__slots__), {"key", "left", "right", "parent"})
        self.assertEqual(BST.__slots__, ("root",))

    def test_inverse_rotations_preserve_middle_subtrees_and_root(self):
        tree = BST()
        for key in [8, 4, 12, 2, 6, 5, 7]:
            tree.insert(key)
        original = structure(tree)
        rotate_right(tree, tree.root)
        self.assertEqual(tree.root.key, 4)
        self.assertEqual(tree.root.right.left.key, 6)
        self.assertEqual(set(tree.depths()), set(original))
        rotate_left(tree, tree.root)
        self.assertEqual(structure(tree), original)
        tree.depths()

    def test_rotation_reconnects_grandparent_and_middle_child(self):
        tree = BST()
        for key in [8, 4, 12, 2, 6, 5, 7]:
            tree.insert(key)
        rotate_left(tree, tree.root.left)
        self.assertEqual(tree.root.left.key, 6)
        self.assertEqual(tree.root.left.left.right.key, 5)
        self.assertEqual(len(tree.depths()), 7)

    def test_invalid_rotations_do_not_modify_tree(self):
        tree = BST()
        tree.insert(1)
        for rotate in (rotate_up, rotate_left, rotate_right):
            with self.assertRaises(ValueError):
                rotate(tree, tree.root)
            self.assertEqual(tree.depths(), {1: 0})

    def test_validation_detects_bad_links_and_order(self):
        tree = BST()
        root = tree.insert(2).node
        child = tree.insert(1).node
        child.parent = None
        with self.assertRaisesRegex(AssertionError, "parent link"):
            tree.depths()
        child.parent = root
        child.key = 3
        with self.assertRaisesRegex(AssertionError, "bound"):
            tree.depths()
        child.key = 1
        child.left = root
        with self.assertRaisesRegex(AssertionError, "cycle"):
            tree.depths()

    def test_custom_strategy_needs_no_change_to_base_tree(self):
        class PromoteNewLeaf:
            def rebalance(self, context):
                if context.inserted.parent is not None:
                    context.promote(context.inserted, 0)

        tree = TreeFlavor(PromoteNewLeaf())
        tree.insert(2)
        stats = tree.insert(1)
        self.assertEqual(tree.tree.root.key, 1)
        self.assertEqual(stats.rotations, 1)
        self.assertEqual(tree.tree.depths(), {1: 0, 2: 1})
        duplicate = tree.insert(2)
        self.assertFalse(duplicate.inserted)
        self.assertEqual(duplicate.rotations, 0)

    def test_deep_tree_uses_no_recursive_traversal(self):
        tree = BST()
        for key in range(1200):
            tree.insert(key)
        self.assertEqual(tree.depths()[1199], 1199)
        self.assertTrue(tree.contains(1199))
        self.assertFalse(tree.contains(1200))
