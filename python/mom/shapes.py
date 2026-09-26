"""Builtin graph shapes over the same catalog — separate graphs, not modes.

Each builder returns a GraphSpec. `register_builtin_shapes` installs only
shapes whose required model ids are present (or registers all and lets
`GraphRegistry.available` filter).
"""

from __future__ import annotations

from mom.directory import ModelDirectory
from mom.graph import Graph
from mom.registry import GraphRegistry, GraphSpec


def shape_speculate_chat() -> GraphSpec:
    """Router overlaps likely generator (latency-hideable on hit)."""
    g = (
        Graph()
        .add("router", "stub.decision")
        .add("gen", "stub.slm")
        .speculate("router", "gen")
    )
    return GraphSpec(
        name="speculate_chat",
        graph=g,
        shape="speculate",
        requires=frozenset({"stub.decision", "stub.slm", "stub.llm"}),
        latency_hideable=True,
        description="decision ∥ speculate(slm); miss falls through to llm",
        tags=frozenset({"chat", "speculate", "hideable"}),
    )


def shape_route_serial() -> GraphSpec:
    """Router then generator — correct but not overlapped (seam visible)."""
    g = (
        Graph()
        .add("router", "stub.decision")
        .add("gen", "stub.slm")
        .link("router", "gen")
    )
    return GraphSpec(
        name="route_serial",
        graph=g,
        shape="route",
        requires=frozenset({"stub.decision", "stub.slm"}),
        latency_hideable=False,
        description="decision → gen serially (route signal is the hop input)",
        tags=frozenset({"chat", "route"}),
    )


def shape_pipeline_transform() -> GraphSpec:
    """Unrelated transform pipeline (third-model style)."""
    g = (
        Graph()
        .add("classify", "stub.classifier")
        .add("flip", "stub.reverse")
        .link("classify", "flip")
    )
    return GraphSpec(
        name="pipeline_transform",
        graph=g,
        shape="pipeline",
        requires=frozenset({"stub.classifier", "stub.reverse"}),
        latency_hideable=False,
        description="classifier → reverse; sequential, no speculation",
        tags=frozenset({"pipeline", "transform"}),
    )


def shape_fanout_reconcile() -> GraphSpec:
    """Parallel generators then serial reconcile (reconcile not hideable)."""
    g = (
        Graph()
        .add("a", "stub.slm")
        .add("b", "stub.llm")
        .add("merge", "stub.reconcile")
        .link("a", "merge")
        .link("b", "merge")
    )
    return GraphSpec(
        name="fanout_reconcile",
        graph=g,
        shape="fanout_reconcile",
        requires=frozenset({"stub.slm", "stub.llm", "stub.reconcile"}),
        latency_hideable=False,
        description="slm ∥ llm → reconcile; fan-out hides max(gen), merge does not",
        tags=frozenset({"fanout", "reconcile"}),
    )


def shape_embed_score() -> GraphSpec:
    """Embedding hop then similarity (optional embedding bus)."""
    g = (
        Graph()
        .add("embed", "stub.embedder.raw")
        .add("score", "stub.similarity")
        .link("embed", "score")
    )
    return GraphSpec(
        name="embed_score",
        graph=g,
        shape="embed",
        requires=frozenset({"stub.embedder.raw", "stub.similarity"}),
        latency_hideable=False,
        description="embed → similarity; sequential vector hop",
        tags=frozenset({"embed", "retrieval"}),
    )


def shape_vision_caption() -> GraphSpec:
    g = Graph().add("cap", "stub.vision.local")
    return GraphSpec(
        name="vision_caption",
        graph=g,
        shape="single",
        requires=frozenset({"stub.vision.local"}),
        latency_hideable=True,
        description="single vision caption model",
        tags=frozenset({"vision"}),
    )


BUILTIN_SHAPES = (
    shape_speculate_chat,
    shape_route_serial,
    shape_pipeline_transform,
    shape_fanout_reconcile,
    shape_embed_score,
    shape_vision_caption,
)


def register_builtin_shapes(
    registry: GraphRegistry,
    directory: ModelDirectory | None = None,
    *,
    only_available: bool = False,
) -> GraphRegistry:
    """Install builtin shapes. If `only_available`, skip unmet requires."""
    for builder in BUILTIN_SHAPES:
        spec = builder()
        if only_available and directory is not None and not spec.satisfied_by(directory):
            continue
        if spec.name not in registry:
            registry.register(spec)
    return registry
