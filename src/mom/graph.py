"""Graphs as runtime data — nodes are directory ids, not hardcoded kinds.

Stable SDK surface: `Graph.add` / `link` / `speculate` / `to_dict` / `from_dict`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass
class Node:
    """A hop in the pipeline; `model_id` points into ModelDirectory."""

    name: str
    model_id: str


@dataclass
class Edge:
    """Directed dependency or speculative overlap."""

    frm: str
    to: str
    kind: Literal["depend", "speculate"] = "depend"

    def to_wire(self) -> dict[str, str]:
        return {"from": self.frm, "to": self.to, "kind": self.kind}


@dataclass
class Graph:
    """Topology as data. Assemble in Python; plan/execute via scheduler."""

    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def add(self, name: str, model_id: str) -> Graph:
        if any(n.name == name for n in self.nodes):
            raise ValueError(f"duplicate node name: {name}")
        self.nodes.append(Node(name=name, model_id=model_id))
        return self

    def link(self, frm: str, to: str) -> Graph:
        self._require(frm)
        self._require(to)
        self.edges.append(Edge(frm=frm, to=to, kind="depend"))
        return self

    def speculate(self, router: str, prior: str) -> Graph:
        """Start `prior` when `router` starts (route-then-run overlap)."""
        self._require(router)
        self._require(prior)
        self.edges.append(Edge(frm=router, to=prior, kind="speculate"))
        return self

    def _require(self, name: str) -> None:
        if not any(n.name == name for n in self.nodes):
            raise KeyError(f"unknown node: {name}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [e.to_wire() for e in self.edges],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Graph:
        """Rebuild a graph from `to_dict()` / JSON wire format."""
        g = cls()
        for n in data.get("nodes") or []:
            g.add(str(n["name"]), str(n["model_id"]))
        for e in data.get("edges") or []:
            kind = e.get("kind", "depend")
            frm = e.get("from", e.get("frm"))
            to = e.get("to")
            if frm is None or to is None:
                raise ValueError(f"invalid edge: {e}")
            if kind == "speculate":
                g.speculate(str(frm), str(to))
            else:
                g.link(str(frm), str(to))
        return g

    def copy(self) -> Graph:
        return Graph.from_dict(self.to_dict())

    def node(self, name: str) -> Node:
        for n in self.nodes:
            if n.name == name:
                return n
        raise KeyError(f"unknown node: {name}")


__all__ = ["Edge", "Graph", "Node"]
