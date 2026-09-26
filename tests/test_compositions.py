"""Sessions, fan-out, registry shapes, concurrency limits, cancel."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from mom import (
    ConcurrencyLimits,
    Graph,
    GraphRegistry,
    GraphSpec,
    LimitExceeded,
    Limiter,
    ModelDirectory,
    Session,
    StateStore,
    run,
    run_named,
)


def test_multi_turn_session(directory, speculate_graph):
    sess = Session(directory, speculate_graph)
    r1 = sess.say("one")
    r2 = sess.say("two")
    assert sess.turns == 2
    assert len(sess.messages) >= 4  # user+assistant × 2
    assert r1.output["model"] == "fast"
    assert r2.output["model"] == "fast"


def test_pipeline_serial_shape(directory):
    g = Graph().add("a", "fast").add("b", "slow").link("a", "b")
    r = run(g, "pipe", directory, state=StateStore())
    assert r.output["model"] == "slow"
    assert r.metrics["total_ms"] >= r.metrics["node_ms"]["a"]


def test_fanout_reconcile_overlap(directory):
    g = (
        Graph()
        .add("a", "fast")
        .add("b", "llm")
        .add("merge", "reconcile")
        .link("a", "merge")
        .link("b", "merge")
    )
    r = run(g, "both", directory, state=StateStore())
    assert r.output["model"] == "reconcile"
    assert "fast" in r.output.get("sources", [])
    waves = r.metrics.get("waves") or []
    assert any(w.get("type") == "parallel" for w in waves)
    a = r.metrics["node_ms"]["a"]
    b = r.metrics["node_ms"]["b"]
    assert r.metrics["critical_path_ms"] < a + b + 5


def test_speculate_miss_cancels_prior(directory, speculate_graph):
    st = StateStore()
    st.set("route", "llm")
    r = run(speculate_graph, "cancel-me", directory, state=st)
    assert (r.metrics.get("spec") or {}).get("router") == "miss"
    assert r.metrics.get("prior_cancelled") is True
    assert float(r.metrics.get("prior_cancelled_ms") or 999) < 40.0


def test_limiter_rejects_under_pressure(directory):
    g = Graph().add("g", "slow")
    lim = Limiter(ConcurrencyLimits(max_runs=1, acquire_timeout_s=0.01))
    rejected = 0
    ok = 0

    def one(_):
        nonlocal rejected, ok
        try:
            from mom import Scheduler

            Scheduler(directory, limits=lim).run(g, "x", StateStore())
            ok += 1
        except LimitExceeded:
            rejected += 1

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(one, range(8)))
    assert ok >= 1
    assert rejected >= 1


def test_custom_registry_heuristic_and_run_named(directory):
    """SDK consumer: own GraphRegistry over their directory ids (not stub.*)."""
    reg = GraphRegistry()
    chat = GraphSpec(
        name="sdk_chat",
        graph=(
            Graph()
            .add("router", "router")
            .add("gen", "fast")
            .speculate("router", "gen")
        ),
        shape="speculate",
        requires=frozenset({"router", "fast"}),
        latency_hideable=True,
        description="sdk consumer speculate",
        tags=frozenset({"chat"}),
    )
    fan = GraphSpec(
        name="sdk_fan",
        graph=(
            Graph()
            .add("a", "fast")
            .add("b", "llm")
            .add("merge", "reconcile")
            .link("a", "merge")
            .link("b", "merge")
        ),
        shape="fanout_reconcile",
        requires=frozenset({"fast", "llm", "reconcile"}),
        latency_hideable=False,
        tags=frozenset({"fanout"}),
    )
    reg.register(chat)
    reg.register(fan)
    assert set(reg.available_names(directory)) == {"sdk_chat", "sdk_fan"}
    r = run_named("sdk_chat", "hi", directory, reg, state=StateStore())
    assert r.metrics["graph"] == "sdk_chat"
    assert (r.metrics.get("spec") or {}).get("router") == "hit"

    r2 = run_named("sdk_fan", "merge views", directory, reg, state=StateStore())
    assert r2.metrics["graph"] == "sdk_fan"
    assert r2.output["model"] == "reconcile"


def test_registry_only_available_ids():
    from mom import register_builtin_shapes

    reg = GraphRegistry()
    register_builtin_shapes(reg)
    empty = ModelDirectory()
    assert reg.available_names(empty) == []
