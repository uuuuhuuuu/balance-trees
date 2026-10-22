"""The seven insertion-order families in Table 2 of the reference paper."""

from random import Random

ORDERS = (
    "random",
    "increasing",
    "decreasing",
    "converging",
    "pairs",
    "bitonic",
    "runs",
)


def insertion_order(name: str, n: int, seed: int) -> list[int]:
    if n < 1:
        raise ValueError("size must be positive")
    if name not in ORDERS:
        raise ValueError(f"unknown insertion order: {name}")
    if name == "random":
        values = list(range(1, n + 1))
        Random(seed).shuffle(values)
        return values
    if name == "increasing":
        return list(range(1, n + 1))
    if name == "decreasing":
        return list(range(n, 0, -1))
    if name == "converging":
        values = []
        low, high = 1, n
        while low <= high:
            values.append(low)
            if low != high:
                values.append(high)
            low += 1
            high -= 1
        return values
    if name == "pairs":
        values = []
        for low in range(1, n + 1, 2):
            if low < n:
                values.append(low + 1)
            values.append(low)
        return values
    evens = list(range(2, n + 1, 2))
    odds = list(range(1, n + 1, 2))
    return evens + (odds[::-1] if name == "bitonic" else odds)
