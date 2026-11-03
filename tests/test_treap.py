import itertools
import unittest
from random import Random

from balance_trees.treap import Treap, TreapNode


class ScriptedRandom:
    def __init__(self, values):
        self.values = iter(values)

    def getrandbits(self, width):
        assert width == 64
        return next(self.values)


def topology(tree):
    result = {}
    stack = [tree.root] if tree.root else []
    while stack:
        node = stack.pop()
        result[node.key] = (node.left.key if node.left else None, node.right.key if node.right else None, node.priority)
        stack.extend(child for child in (node.left, node.right) if child)
    return result


class TreapTests(unittest.TestCase):
    def test_empty_root_lookup_and_duplicate_randomness(self):
        tree = Treap(7)
        self.assertEqual(tree.validate(), {})
        self.assertFalse(tree.contains(4))
        first = tree.insert(4)
        self.assertEqual(first.insertion_depth, 0)
        self.assertEqual(first.random_bits, 64)
        state = tree._random.getstate()
        before = topology(tree)
        duplicate = tree.insert(4)
        self.assertFalse(duplicate.inserted)
        self.assertEqual(duplicate.random_bits, 0)
        self.assertEqual(duplicate.rotations, 0)
        self.assertEqual(state, tree._random.getstate())
        self.assertEqual(before, topology(tree))
        self.assertTrue(tree.contains(4))

    def test_records_depth_before_promoting_to_root(self):
        tree = Treap()
        tree._random = ScriptedRandom([100, 80, 10])
        tree.insert(2)
        tree.insert(1)
        stats = tree.insert(3)
        self.assertEqual(stats.insertion_depth, 2)
        self.assertEqual(stats.rotations, 2)
        self.assertEqual(tree.validate()[3], 0)

    def test_priority_ties_use_keys(self):
        tree = Treap()
        tree._random = ScriptedRandom([10] * 4)
        for key in [3, 1, 4, 2]:
            tree.insert(key)
            tree.validate()
        self.assertEqual(tree.root.key, 1)

    def test_small_permutations_match_independent_cartesian_reference(self):
        def reference(items):
            if not items:
                return {}
            root = min(items, key=lambda pair: (pair[1], pair[0]))
            left = [pair for pair in items if pair[0] < root[0]]
            right = [pair for pair in items if pair[0] > root[0]]
            left_root = min(left, key=lambda pair: (pair[1], pair[0]))[0] if left else None
            right_root = min(right, key=lambda pair: (pair[1], pair[0]))[0] if right else None
            return {root[0]: (left_root, right_root, root[1]), **reference(left), **reference(right)}
        for keys in itertools.permutations(range(5)):
            tree = Treap(17)
            assigned = []
            for key in keys:
                node = tree.root
                expected_depth = 0
                while node is not None:
                    node = node.left if key < node.key else node.right
                    expected_depth += 1
                stats = tree.insert(key)
                self.assertEqual(stats.insertion_depth, expected_depth)
                assigned.append((key, stats.priority))
                self.assertEqual(set(tree.validate()), {k for k, _ in assigned})
                self.assertEqual(topology(tree), reference(assigned))

    def test_sorted_reverse_and_random_inputs(self):
        shuffled = list(range(2000))
        Random(32).shuffle(shuffled)
        for keys in (range(2000), range(1999, -1, -1), shuffled):
            tree = Treap(19)
            for index, key in enumerate(keys):
                tree.insert(key)
                if index % 100 == 0:
                    tree.validate()
            self.assertEqual(set(tree.validate()), set(range(2000)))
            self.assertTrue(tree.contains(1999))
            self.assertFalse(tree.contains(-1))

    def test_deep_chain_is_iterative(self):
        tree = Treap()
        previous = None
        for key in range(3000):
            node = TreapNode(key, parent=previous, priority=key + 100)
            if previous is None:
                tree.root = node
            else:
                previous.right = node
            previous = node
        tree._random = ScriptedRandom([0])
        stats = tree.insert(3000)
        self.assertEqual(stats.insertion_depth, 3000)
        self.assertEqual(stats.rotations, 3000)
        self.assertEqual(len(tree.validate()), 3001)

    def test_validation_detects_heap_corruption(self):
        tree = Treap(2)
        tree.insert(1)
        tree.insert(2)
        child = tree.root.left or tree.root.right
        child.priority = -1
        with self.assertRaises(AssertionError):
            tree.validate()


if __name__ == '__main__':
    unittest.main()
