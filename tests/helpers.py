from balance_trees.random_bits import RandomBits


class FixedBits(RandomBits):
    """An exact scripted bit stream; exhaustion fails the test immediately."""

    def __init__(self, values):
        self.values = iter(values)
        self.count = 0

    def bit(self):
        self.count += 1
        return next(self.values)


class Decisions(RandomBits):
    """Script coin outcomes to test traversal independently of coin sampling."""

    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.probabilities = []
        self.count = 0

    def bernoulli(self, numerator, denominator):
        self.probabilities.append((numerator, denominator))
        return next(self.outcomes)
