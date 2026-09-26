"""Speculation, cancel, prior — production-style correctness."""

from __future__ import annotations

from mom import Graph, LightPrior, StateStore, run


def test_speculate_hit(directory, speculate_graph):
    r = run(speculate_graph, "hi", directory, state=StateStore())
    assert (r.metrics.get("spec") or {}).get("router") == "hit"
    assert r.output["model"] == "fast"
    # Overlap: total should be near max(router, prior), not sum
    assert r.metrics["total_ms"] < 50.0


def test_speculate_miss_runs_routed(directory, speculate_graph):
    st = StateStore()
    st.set("route", "llm")
    r = run(speculate_graph, "hard", directory, state=st)
    assert (r.metrics.get("spec") or {}).get("router") == "miss"
    assert r.output["model"] == "llm"
    assert r.metrics.get("prior_cancelled") is True or r.metrics["total_ms"] > 40


def test_light_prior_flips_model_id(directory):
    graph = (
        Graph()
        .add("router", "router")
        .add("gen", "fast")
        .speculate("router", "gen")
    )
    prior = LightPrior(
        default="fast",
        candidates=("fast", "llm"),
        feature_key=None,
        min_observations=3,
    )
    # Force miss path so prior learns llm
    for _ in range(4):
        st = StateStore()
        st.set("route", "llm")
        run(graph, "x" * 90, directory, state=st, prior=prior)
    st = StateStore()
    st.set("route", "llm")
    suggested = prior.suggest("x" * 90, st)
    assert suggested == "llm"
    r = run(graph, "x" * 90, directory, state=st, prior=prior)
    assert r.metrics.get("prior_suggested") == "llm"
    assert (r.metrics.get("spec") or {}).get("router") == "hit"
    assert r.output["model"] == "llm"
