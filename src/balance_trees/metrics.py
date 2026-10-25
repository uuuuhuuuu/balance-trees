"""Measurements live outside the tree and its nodes."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class InsertionStats:
    inserted: bool
    insertion_depth: int
    visits: int = 0
    random_bits: int = 0
    rotation_distances: list[int] = field(default_factory=list)
    scanned_nodes: int = 0
    priority: int | None = None

    @property
    def rotations(self) -> int:
        return len(self.rotation_distances)


@dataclass(frozen=True, slots=True)
class TrialMetrics:
    mean_depth: float
    height: int
    mean_insertion_depth: float
    mean_rotations: float
    max_rotations: int
    mean_visits: float
    max_visits: int
    mean_random_bits: float
    max_random_bits: int
    mean_scanned_nodes: float = 0
    max_scanned_nodes: int = 0
