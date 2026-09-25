"""Graphs as runtime data — nodes are directory ids, not hardcoded kinds."""

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
        self.nodes.append(Node(name=name, model_id=model_id))
        return self

    def link(self, frm: str, to: str) -> Graph:
        self.edges.append(Edge(frm=frm, to=to, kind="depend"))
        return self

    def speculate(self, router: str, prior: str) -> Graph:
        """Start `prior` when `router` starts (route-then-run overlap)."""
        self.edges.append(Edge(frm=router, to=prior, kind="speculate"))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [e.to_wire() for e in self.edges],
        }

    def node(self, name: str) -> Node:
        for n in self.nodes:
            if n.name == name:
                return n
        raise KeyError(f"unknown node: {name}")
