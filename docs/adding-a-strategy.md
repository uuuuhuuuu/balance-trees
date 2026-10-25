# Adding a strategy

A flavor composes `TreeFlavor` with a strategy object. The strategy implements a
single method; there is no subclass requirement and no change to `BST`.

For example, this deterministic control strategy always promotes the new leaf
once. It is useful as a comparison, although it does not guarantee good depths.

```python
from dataclasses import dataclass

from balance_trees.strategies import RebalanceContext


@dataclass(frozen=True, slots=True)
class AlwaysPromoteLeaf:
    def rebalance(self, context: RebalanceContext) -> None:
        if context.inserted.parent is not None:
            context.stats.visits += 1
            context.promote(context.inserted, distance=0)
```

Register a descriptor in `strategies/__init__.py` to expose it to the demo,
experiment and local benchmark CLIs:

```python
"always-leaf": StrategySpec(
    AlwaysPromoteLeaf,
    "Always promote leaf", "Deterministic control",
    "Promote the inserted leaf once; no balance guarantee.",
),
```

`StrategyFactory.register(name, spec)` also supports registrations in a custom
driver. Duplicate names are rejected. Use `create_strategy(name, **options)`
or `TreeFlavor.create(name, seed=2026, **options)` to obtain a new policy/tree.
`STRATEGIES` remains an iterable of callable descriptors for existing clients.
The factory is the shared source for creation and display metadata. Every trial
gets a fresh policy; this is essential for `random-level`, whose count and
priority extrema belong to one tree. Keep immutable configuration and document
any persistent external state.

For the website, implement one generator factory in `site/dist/strategies.mjs`
with `registerStrategy(name, context => function* (node, insertionDepth) {...})`.
Both browser engines supply adapters for `parent`, `left`, `right`, `key`,
`choose`, `promote`, `scan`, `event`, `visit` and `bit`. Missing implementations
fail with a descriptive error rather than quietly using plain BST insertion.
Do not modify the insertion engines or tree renderer for a new policy.

Refresh the local metadata catalog after changing a descriptor:

```sh
PYTHONPATH=src python3 -m balance_trees.showcase.build --sync-catalog
```

Static builds regenerate it automatically. The catalog parity test detects
stale local metadata, and browser tests check that every catalog entry has a
factory and that detailed/worker outcomes agree.

For a randomized strategy, use the supplied `context.bits` exclusively for
fresh random draws. A recomputed-priority strategy may use `context.seed` as
fixed external configuration, with its assumptions documented. Global
randomness makes replay and random-bit accounting unreliable. For a new rule
under the paper's stopping policy, implement `apply(context, node, distance)`
and supply it to `GeometricStop`.

A rotation distance is the number of edges on the original insertion path from
the inserted leaf to the node being promoted. Define how your traversal updates
this distance when rotations change the path; do not silently report decision
indices as path distances. Multiple promotions count as multiple rotations.

Tests should exercise all local configurations, missing ancestors, root changes,
middle-subtree transfers, duplicate insertions, and deterministic random streams.
Validate the complete tree after each insertion in small exhaustive tests. Test
new algorithms' rotation limits explicitly rather than assuming they inherit
the limits of the existing baselines.


For structural reconstruction, call `context.scan(node)` for every actual node
inspection. Never read measurement or visualization caches to make an algorithm
look cheaper. `context.compare_priority(...)` records recomputed-priority
comparisons without consuming fair bits. The showcase context observes both
primitives. See [the priority-free strategies](priority-free-strategies.md) for
examples sharing temporary counts without adding node fields.
