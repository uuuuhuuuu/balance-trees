"""Random-level v2.1: local repairs with logarithmically wide priorities."""

from dataclasses import dataclass

from .base import RebalanceContext
from .random_level_v2 import RandomLevelV2


@dataclass(slots=True)
class RandomLevelV21(RandomLevelV2):
    """Use ceil(log2(k + 1)) fresh random bits for the k-th insertion.

    The first insertion uses one bit, the second uses two, and so on. The
    resulting priority is a uniform integer in [0, 2**bits). The v2 target
    selection and local-repair mechanics are unchanged.

    Because the sampled range widens over time, a new priority can exceed the
    previous maximum and remain a leaf, or fall below the previous minimum and
    be promoted to the root. This preserves the v2 invariant that strict new
    minima reach the root. It does not preserve a fixed 64-bit priority
    distribution across the run; priorities drawn later have a wider range.
    """

    def roll_priority(self, context: RebalanceContext) -> int:
        """Sample one priority using a growing logarithmic bit width."""
        bits = max(1, (self.inserted_count + 1).bit_length())
        value = 0
        for _ in range(bits):
            value = (value << 1) | context.bits.bit()
        return value
