"""Registry of model adapters — id → factory + metadata.

Mirrors registrations into `mom._native.ModelDirectory` when the extension
is loaded so `run_graph` can invoke the same catalog.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from mom.adapter import Model

ModelFactory = Callable[[], Model]

try:
    from mom._native import ModelDirectory as _NativeDirectory
except ImportError:
    _NativeDirectory = None


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
        self._native = _NativeDirectory() if _NativeDirectory is not None else None

    @property
    def native(self) -> Any:
        """Underlying native directory, or None if extension missing."""
        return self._native

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
        tag_set = frozenset(tags or ())
        self._entries[id] = ModelEntry(
            id=id,
            factory=factory,
            tags=tag_set,
            meta=dict(meta),
        )
        if self._native is not None:
            # Native callables: (input, state) -> output
            def _call(
                inp: Any,
                state: Any,
                _factory: ModelFactory = factory,
            ) -> Any:
                return _factory().run(inp, state)

            self._native.register(id, _call, tags=sorted(tag_set))

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
