"""Exact rational Bernoulli trials, counted in logical fair random bits."""

from random import Random


class RandomBits:
    def __init__(self, seed: int):
        self._random = Random(seed)
        self.count = 0

    def bit(self) -> int:
        self.count += 1
        return self._random.getrandbits(1)

    def bernoulli(self, numerator: int, denominator: int) -> bool:
        """Compare a lazy uniform binary expansion with numerator/denominator.

        Unlike float comparisons this handles arbitrarily small probabilities.
        Each nontrivial trial uses at most two fair bits in expectation, although
        the number of trials per insertion need not be constant.
        """
        if denominator <= 0 or not 0 <= numerator <= denominator:
            raise ValueError("probability must be between zero and one")
        if numerator == 0:
            return False
        if numerator == denominator:
            return True
        remainder = numerator
        while True:
            threshold_bit, remainder = divmod(2 * remainder, denominator)
            uniform_bit = self.bit()
            if uniform_bit != threshold_bit:
                return uniform_bit < threshold_bit
            if remainder == 0:
                return False
