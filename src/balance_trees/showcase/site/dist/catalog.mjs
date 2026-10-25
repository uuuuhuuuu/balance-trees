// Generated from the Python strategy factory by showcase.build.
export const FLAVORS = {
  "treap": {
    "name": "Treap",
    "tag": "Priority heap",
    "note": "A BST by key and min-heap by stored random priority. This browser reference retains per-node priorities."
  },
  "halving": {
    "name": "Halving walk",
    "tag": "Full upward walk",
    "note": "Try 1/2, 1/4, 1/8… and continue to the root after either outcome. Expected fewer than one rotation per insertion; ancestor work can be linear."
  },
  "constant-half": {
    "name": "Constant ½",
    "tag": "Full upward walk",
    "note": "Rotate with probability 1/2 at every visited ancestor, continuing to the root. Both visits and rotations can grow with depth."
  },
  "inverse-depth": {
    "name": "Inverse depth",
    "tag": "Depth-informed rule",
    "note": "Freeze initial insertion depth h and use 1/h at every decision. Sorted inputs produce a chain despite at most one expected rotation."
  },
  "none": {
    "name": "Plain BST",
    "tag": "No rebalancing",
    "note": "Ordinary leaf insertion. Ordered inputs can produce linear height and quadratic insertion work."
  },
  "paper-zig": {
    "name": "Paper · Zig",
    "tag": "Geometric stop",
    "note": "Continue upward with probability 1/2; otherwise promote the cursor once and stop."
  },
  "paper-zigzag": {
    "name": "Paper · ZigZag",
    "tag": "Geometric stop",
    "note": "Continue with probability 3/4. On stopping, a straight path promotes the parent once, a bent path promotes the cursor twice."
  },
  "recount-root": {
    "name": "Recount root lottery",
    "tag": "Exact distribution",
    "note": "Exact random-BST shape distribution from empty, using transient full-tree counting. Linear scan work per insertion; quadratic total scans."
  },
  "window-root": {
    "name": "Window root lottery",
    "tag": "Bounded local heuristic",
    "note": "Root lotteries within 64 actual node inspections by default. Never uses an incomplete count; no general logarithmic-depth guarantee."
  },
  "hash-priority": {
    "name": "Recomputed priority",
    "tag": "Keyed hash heuristic",
    "note": "Recompute SplitMix64 key/seed priorities for treap-style comparisons. No priority table or fresh insertion bits; finite hashes are not independent priorities."
  },
  "random-level": {
    "name": "Random level",
    "tag": "Priority-free depth heuristic",
    "note": "Roll 64 fair bits and choose a depth from the previous observed priority interval. New minima reach the root; new maxima stay leaves. Stores only a count and two extrema; no balance guarantee."
  }
};
