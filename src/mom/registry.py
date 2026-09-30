"""Named graph registry — topology as data, keyed by name.

Graphs are separate definitions (not mode flags). A registry entry can declare
required directory ids and whether the shape is latency-hideable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from mom.directory import ModelDirectory
from mom.graph import Graph


@dataclass(frozen=True)
class GraphSpec:
    """One named composition over directory ids."""

    name: str
    graph: Graph
    shape: str
    requires: frozenset[str] = field(default_factory=frozenset)
    latency_hideable: bool = True
    description: str = ""
    tags: frozenset[str] = field(default_factory=frozenset)

    def satisfied_by(self, directory: ModelDirectory) -> bool:
        return all(mid in directory for mid in self.requires)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "shape": self.shape,
            "requires": sorted(self.requires),
            "latency_hideable": self.latency_hideable,
            "description": self.description,
            "tags": sorted(self.tags),
            "graph": self.graph.to_dict(),
        }


class GraphRegistry:
    """name → GraphSpec. Pick only graphs whose models exist in the directory."""

    def __init__(self) -> None:
        self._specs: dict[str, GraphSpec] = {}

    def register(self, spec: GraphSpec) -> None:
        if spec.name in self._specs:
            raise KeyError(f"graph already registered: {spec.name}")
        self._specs[spec.name] = spec

    def get(self, name: str) -> GraphSpec:
        try:
            return self._specs[name]
        except KeyError as e:
            raise KeyError(f"unknown graph: {name}") from e

    def names(self) -> list[str]:
        return sorted(self._specs)

    def specs(self) -> list[GraphSpec]:
        return [self._specs[n] for n in self.names()]

    def available(self, directory: ModelDirectory) -> list[GraphSpec]:
        return [s for s in self.specs() if s.satisfied_by(directory)]

    def available_names(self, directory: ModelDirectory) -> list[str]:
        return [s.name for s in self.available(directory)]

    def pick(
        self,
        directory: ModelDirectory,
        name: str | None = None,
        *,
        selector: Callable[["GraphRegistry", ModelDirectory, Any, Any], str]
        | None = None,
        input: Any = None,
        state: Any = None,
    ) -> GraphSpec:
        """
        Resolve a graph: explicit `name`, else `selector`, else first available
        latency-hideable spec (then any available).
        """
        if name is not None:
            spec = self.get(name)
            if not spec.satisfied_by(directory):
                missing = sorted(mid for mid in spec.requires if mid not in directory)
                raise KeyError(
                    f"graph '{name}' needs models not in directory: {missing}"
                )
            return spec
        if selector is not None:
            chosen = selector(self, directory, input, state)
            return self.pick(directory, chosen)
        avail = self.available(directory)
        if not avail:
            raise KeyError("no registered graphs are satisfied by the directory")
        hideable = [s for s in avail if s.latency_hideable]
        return (hideable or avail)[0]

    def __contains__(self, name: str) -> bool:
        return name in self._specs

    def __len__(self) -> int:
        return len(self._specs)
