"""Descriptors and factories shared by CLIs, benchmarks and the showcase."""

from collections.abc import Callable
from dataclasses import dataclass

from .base import Strategy


@dataclass(frozen=True, slots=True)
class StrategySpec:
    factory: Callable[..., Strategy]
    name: str
    tag: str
    note: str

    def __call__(self, **options) -> Strategy:
        """Always return a fresh policy, including for stateful strategies."""
        return self.factory(**options)


class StrategyFactory:
    def __init__(self) -> None:
        self.specs: dict[str, StrategySpec] = {}

    def register(self, identifier: str, spec: StrategySpec) -> None:
        if not identifier or identifier in self.specs:
            raise ValueError(f"strategy already registered or empty: {identifier!r}")
        self.specs[identifier] = spec

    def create(self, identifier: str, **options) -> Strategy:
        try:
            spec = self.specs[identifier]
        except KeyError:
            raise ValueError(f"unknown strategy: {identifier!r}") from None
        return spec(**options)

    def catalog(self) -> dict[str, dict[str, str]]:
        return {
            key: {"name": spec.name, "tag": spec.tag, "note": spec.note}
            for key, spec in self.specs.items()
        }
