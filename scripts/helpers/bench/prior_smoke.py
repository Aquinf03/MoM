#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

"""
Light prior: static default → learned likely-winner.
  python bench/prior_smoke.py
"""
from __future__ import annotations
from models import register_builtins
from mom import Graph, LightPrior, ModelDirectory, Scheduler, StateStore
def main() -> None:
    directory = ModelDirectory()
    register_builtins(directory)
    # One prior node; LightPrior swaps its model_id (slm default → llm when learned).
    graph = (
        Graph()
        .add("router", "stub.decision")
        .add("gen", "stub.slm")
        .speculate("router", "gen")
    )
    prior = LightPrior(
        default="stub.slm",
        candidates=("stub.slm", "stub.llm"),
        feature_key="classification",
        min_observations=3,
    )
    sched = Scheduler(directory, prior=prior)
    hard = "please reason carefully about this complex problem " * 2
    for _ in range(5):
        st = StateStore()
        st.set("classification", "hard")
        r = sched.run(graph, hard, st)
        assert r.metrics.get("spec"), r.metrics
    easy_st = StateStore()
    easy_st.set("classification", "easy")
    easy = sched.run(graph, "hi", easy_st)
    easy_suggested = easy.metrics.get("prior_suggested")
    hard_st = StateStore()
    hard_st.set("classification", "hard")
    suggested_hard = prior.suggest(hard, hard_st)
    hard_run = sched.run(graph, hard, hard_st)
    out_model = (
        hard_run.output.get("model")
        if isinstance(hard_run.output, dict)
        else hard_run.output
    )
    snap = prior.snapshot()
    print(f"prior snapshot: {snap}")
    print(f"easy suggested={easy_suggested} (expect stub.slm)")
    print(f"hard suggested={suggested_hard} (expect stub.llm)")
    print(
        f"hard run prior_suggested={hard_run.metrics.get('prior_suggested')} "
        f"spec={hard_run.metrics.get('spec')} out_model={out_model}"
    )
    learned = suggested_hard == "stub.llm"
    easy_ok = easy_suggested == "stub.slm"
    hard_hit = (hard_run.metrics.get("spec") or {}).get("router") == "hit"
    hard_model_ok = out_model == "stub.llm"
    overall = learned and easy_ok and hard_hit and hard_model_ok
    print(f"learned hard→llm:    {'PASS' if learned else 'FAIL'}")
    print(f"easy stays default:  {'PASS' if easy_ok else 'FAIL'}")
    print(f"hard speculation hit:{'PASS' if hard_hit else 'FAIL'}")
    print(f"hard output is llm:  {'PASS' if hard_model_ok else 'FAIL'}")
    print(f"overall: {'PASS' if overall else 'FAIL'}")
    raise SystemExit(0 if overall else 1)
if __name__ == "__main__":
    main()
