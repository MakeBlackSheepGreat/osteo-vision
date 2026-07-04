from __future__ import annotations

from typing import Any, Callable

PipelineFactory = Callable[..., object]


class PipelineRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, PipelineFactory] = {}

    def register(self, name: str, factory: PipelineFactory) -> None:
        self._factories[name] = factory

    def create(self, name: str, **kwargs: Any) -> object:
        if name not in self._factories:
            raise KeyError(f"Unknown pipeline: {name}")
        return self._factories[name](**kwargs)

    def names(self) -> list[str]:
        return sorted(self._factories)
