"""Registry of model adapters — id → factory + metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from mom.adapter import Model

ModelFactory = Callable[[], Model]


@dataclass
class ModelEntry:
    id: str
    factory: ModelFactory
    tags: frozenset[str] = field(default_factory=frozenset)
    meta: dict[str, Any] = field(default_factory=dict)


class ModelDirectory:
    """Growable catalog. Graphs reference entries by id."""

    def __init__(self) -> None:
        self._entries: dict[str, ModelEntry] = {}

    def register(
        self,
        id: str,
        factory: ModelFactory,
        *,
        tags: set[str] | frozenset[str] | None = None,
        **meta: Any,
    ) -> None:
        if id in self._entries:
            raise KeyError(f"model already registered: {id}")
        self._entries[id] = ModelEntry(
            id=id,
            factory=factory,
            tags=frozenset(tags or ()),
            meta=dict(meta),
        )

    def get(self, id: str) -> ModelEntry:
        try:
            return self._entries[id]
        except KeyError as e:
            raise KeyError(f"unknown model: {id}") from e

    def create(self, id: str) -> Model:
        return self.get(id).factory()

    def ids(self) -> list[str]:
        return sorted(self._entries)

    def __contains__(self, id: str) -> bool:
        return id in self._entries

    def __len__(self) -> int:
        return len(self._entries)
