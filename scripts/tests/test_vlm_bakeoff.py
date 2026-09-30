"""
Bakeoff: big VLM vs MoM(ViT + router + SLM/LLM).

Validates the composition thesis with timed stub specialists (CI-safe).
Swap bakeoff.* factories for real ViT/VLM/SLM adapters later — same graphs.
"""

from __future__ import annotations

import statistics

import pytest

from mom import ModelDirectory, StateStore, plan_graph, run
from scripts.tests.vlm_bakeoff import (
    graph_mom_specialists,
    graph_monolith,
    register_bakeoff,
)


@pytest.fixture
def bakeoff_dir() -> ModelDirectory:
    d = ModelDirectory()
    register_bakeoff(d)
    return d


def _sample(image: str, question: str) -> dict[str, str]:
    return {"image": image, "question": question, "text": question}


def test_bakeoff_ids_registered(bakeoff_dir: ModelDirectory):
    for mid in (
        "bakeoff.vlm",
        "bakeoff.vit",
        "bakeoff.router",
        "bakeoff.slm",
        "bakeoff.llm",
    ):
        assert mid in bakeoff_dir


def test_monolith_graph_is_single_hop(bakeoff_dir: ModelDirectory):
    g = graph_monolith()
    plan = plan_graph(g)
    assert plan["steps"] == [{"type": "run", "node": "vlm"}]
    r = run(g, _sample("img://meter", "what color?"), bakeoff_dir, state=StateStore())
    assert r.output["arm"] == "monolith"
    assert r.output["model"] == "bakeoff.vlm"
    assert "img://meter" in r.output["text"]


def test_mom_graph_is_vit_then_speculate(bakeoff_dir: ModelDirectory):
    g = graph_mom_specialists()
    plan = plan_graph(g)
    types = [s["type"] for s in plan["steps"]]
    assert types == ["run", "speculate"]
    assert plan["steps"][0]["node"] == "vit"
    assert plan["steps"][1]["router"] == "router"
    assert plan["steps"][1]["prior"] == "gen"


def test_mom_easy_hit_uses_slm_and_vit_state(bakeoff_dir: ModelDirectory):
    g = graph_mom_specialists()
    st = StateStore()
    r = run(g, _sample("img://plug", "is it on?"), bakeoff_dir, state=st)
    st = r.state or st
    assert (r.metrics.get("spec") or {}).get("router") == "hit"
    assert r.output["model"] == "bakeoff.slm"
    assert r.output["arm"] == "mom"
    assert st.get("caption")
    assert st.get("embedding")
    assert st.get("vision_path") == "specialists"
    assert "vit:" in str(st.get("caption"))
    assert "vit:" in r.output["text"] or "slm+vit" in r.output["text"]


def test_mom_hard_miss_uses_llm_with_shared_vit(bakeoff_dir: ModelDirectory):
    g = graph_mom_specialists()
    st = StateStore()
    r = run(
        g,
        _sample("img://schematic", "why is this diagram failing?"),
        bakeoff_dir,
        state=st,
    )
    st = r.state or st
    assert (r.metrics.get("spec") or {}).get("router") == "miss"
    assert r.output["model"] == "bakeoff.llm"
    # ViT wrote shared state before language hop
    assert st.get("caption")
    assert st.get("embedding")
    assert "emb_dim=" in r.output["text"]


def test_mom_easy_faster_than_monolith(bakeoff_dir: ModelDirectory):
    """Easy traffic: specialists should beat one big VLM on wall time."""
    mono = graph_monolith()
    mom = graph_mom_specialists()
    prompt = _sample("img://led", "is the light red?")

    mono_ms = []
    mom_ms = []
    for _ in range(5):
        mono_ms.append(
            run(mono, prompt, bakeoff_dir, state=StateStore()).metrics["total_ms"]
        )
        mom_ms.append(
            run(mom, prompt, bakeoff_dir, state=StateStore()).metrics["total_ms"]
        )

    mono_p50 = statistics.median(mono_ms)
    mom_p50 = statistics.median(mom_ms)
    # Engineered stub budgets: VLM 120 vs ViT15+max(router8,slm25)≈40 → MoM clearly faster
    assert mom_p50 < mono_p50 * 0.75, (mom_p50, mono_p50)
    assert mom_p50 < 90.0
    assert mono_p50 > 100.0


def test_shared_state_survives_second_turn_without_reencode_flag(
    bakeoff_dir: ModelDirectory,
):
    """
    Multi-turn: caption from turn 1 remains in store; second hop can read it.

    Full Session re-runs the graph (re-encodes) unless you add a cache node —
    here we prove StateStore holds vision features across manual turns.
    """
    g = graph_mom_specialists()
    st = StateStore()
    r1 = run(g, _sample("img://panel", "status?"), bakeoff_dir, state=st)
    st = r1.state or st
    caption1 = st.get("caption")
    emb1 = list(st.get("embedding") or [])
    assert caption1 and emb1
    assert r1.output["model"] == "bakeoff.slm"

    # Second question, same store — vision features still present before run
    st.set("classification", "hard")
    assert st.get("caption") == caption1
    r2 = run(
        g,
        _sample("img://panel", "why is this failing?"),
        bakeoff_dir,
        state=st,
    )
    st = r2.state or st
    assert r2.output["model"] == "bakeoff.llm"
    # Caption still from ViT path (may refresh; must remain set)
    assert st.get("caption")
    assert st.get("embedding")


def test_forced_route_to_llm(bakeoff_dir: ModelDirectory):
    g = graph_mom_specialists()
    st = StateStore()
    st.set("route", "bakeoff.llm")
    r = run(g, _sample("img://x", "hi"), bakeoff_dir, state=st)
    assert (r.metrics.get("spec") or {}).get("router") == "miss"
    assert r.output["model"] == "bakeoff.llm"
