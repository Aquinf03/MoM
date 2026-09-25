"""Graphs as runtime data — nodes are directory ids, not hardcoded kinds."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Node:
    """A hop in the pipeline; `model_id` points into ModelDirectory."""

    name: str
    model_id: str


@dataclass
class Edge:
    """Directed dependency: `to` waits on `frm`."""

    frm: str
    to: str


@dataclass
class Graph:
    """Topology as data. Assemble in Python; execute later via mom-core."""

    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def add(self, name: str, model_id: str) -> Graph:
        self.nodes.append(Node(name=name, model_id=model_id))
        return self

    def link(self, frm: str, to: str) -> Graph:
        self.edges.append(Edge(frm=frm, to=to))
        return self
