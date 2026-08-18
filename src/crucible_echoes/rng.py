from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, TypeVar

T = TypeVar("T")
MASK = (1 << 64) - 1


@dataclass
class DeterministicRNG:
    """Small JSON-friendly SplitMix64 stream.

    The complete state is one integer, so saves reproduce every future draw.
    """

    state: int

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
        return (z ^ (z >> 31)) & MASK

    def random(self) -> float:
        return (self.next_u64() >> 11) * (1.0 / (1 << 53))

    def randint(self, low: int, high: int) -> int:
        if high < low:
            raise ValueError("high must be >= low")
        return low + self.next_u64() % (high - low + 1)

    def choice(self, values: Sequence[T]) -> T:
        if not values:
            raise IndexError("cannot choose from an empty sequence")
        return values[self.next_u64() % len(values)]

    def shuffle(self, values: list[T]) -> None:
        for i in range(len(values) - 1, 0, -1):
            j = self.next_u64() % (i + 1)
            values[i], values[j] = values[j], values[i]

    def sample(self, values: Sequence[T], count: int) -> list[T]:
        copied = list(values)
        self.shuffle(copied)
        return copied[:count]

    def weighted_choice(self, weighted: Sequence[tuple[T, float]]) -> T:
        total = sum(max(0.0, weight) for _, weight in weighted)
        if total <= 0:
            raise ValueError("weighted choice requires a positive total weight")
        needle = self.random() * total
        upto = 0.0
        for value, weight in weighted:
            upto += max(0.0, weight)
            if needle < upto:
                return value
        return weighted[-1][0]

