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

Register `"always-leaf": AlwaysPromoteLeaf` in `STRATEGIES` to expose it to the
demo and experiment CLIs. Factories create fresh strategy objects for each trial.
Use immutable strategy configuration and keep temporary state inside `rebalance`
to avoid accidentally carrying information across insertions.

For a randomized strategy, use the supplied `context.bits` exclusively. Global
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
