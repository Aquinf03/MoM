"""Stress / production-manner matrix: load, errors, embedding bus, catalog."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from mom import Bus, Graph, LimitExceeded, Scheduler, StateStore, run


def test_concurrent_speculate_hits(directory, speculate_graph):
    def one(i: int):
        return run(speculate_graph, f"msg-{i}", directory, state=StateStore())

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(one, range(12)))
    assert all((r.metrics.get("spec") or {}).get("router") == "hit" for r in results)
    assert all(r.output["model"] == "fast" for r in results)


def test_unknown_model_errors(directory):
    g = Graph().add("g", "nope")
    with pytest.raises(KeyError):
        run(g, "x", directory, state=StateStore())


def test_router_without_route_errors(directory):
    class BadRouter:
        def run(self, input, state, cancel=None):
            return {"nope": True}

    directory.register("bad", BadRouter, tags={"router"})
    g = Graph().add("router", "bad").add("gen", "fast").speculate("router", "gen")
    with pytest.raises(ValueError):
        run(g, "x", directory, state=StateStore())


def test_embedding_bus_passthrough_then_pack(directory):
    class Emb:
        def run(self, input, state, cancel=None):
            vec = [0.1, 0.2, 0.3, 0.4]
            state.set("embedding", vec)
            return vec

    class Score:
        def run(self, input, state, cancel=None):
            assert isinstance(input, list)
            return {"best": "ok", "n": len(input), "model": "score"}

    directory.register("emb", Emb, tags={"embedder"})
    directory.register("score", Score, tags={"similarity"})
    g = Graph().add("e", "emb").add("s", "score").link("e", "s")
    r = run(g, "txt", directory, state=StateStore(), bus=Bus.embedding())
    assert r.output["best"] == "ok"
    assert int(r.metrics.get("bus_hops") or 0) >= 1


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "models").is_dir(),
    reason="repo models/ catalog not present",
)
def test_repo_catalog_via_sdk():
    """Optional: wide stub catalog still works when models/ is on path."""
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root)]
    from models import register_builtins
    from mom import ModelDirectory, register_builtin_shapes, GraphRegistry, run_named

    d = ModelDirectory()
    register_builtins(d)
    assert len(d) >= 20
    reg = register_builtin_shapes(GraphRegistry(), d)
    r = run_named("speculate_chat", "hi", d, reg, state=StateStore())
    assert r.metrics.get("graph") == "speculate_chat"
    assert (r.metrics.get("spec") or {}).get("router") == "hit"
