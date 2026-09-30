#!/usr/bin/env python3
"""Show the seeded model span + a classifier→speculate(SLM) composition."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from models import catalog_ids, register_builtins
from mom import Graph, ModelDirectory, StateStore, ping, plan_graph, run


def main() -> None:
    directory = ModelDirectory()
    register_builtins(directory)

    print(f"native ping: {ping()}")
    print(f"catalog ({len(directory)}): {catalog_ids()}")
    print(f"native directory mirrored: {directory.native is not None}")

    graph = (
        Graph()
        .add("router", "stub.decision")
        .add("fast", "stub.slm")
        .speculate("router", "fast")
    )
    print(f"plan: {plan_graph(graph)}")

    state_hit = StateStore()
    hit = run(graph, "hi", directory, state=state_hit)
    m = hit.metrics
    print(
        f"HIT  spec={m.get('spec')} total={m['total_ms']:.1f}ms "
        f"orch={m.get('orchestration_overhead_ms', 0):.1f}ms "
        f"router={m.get('router_ms', 0):.1f} model={m.get('model_ms', 0):.1f} "
        f"out={hit.output!r}"
    )

    state_miss = StateStore()
    state_miss.set("classification", "hard")
    miss = run(graph, "please reason carefully", directory, state=state_miss)
    m = miss.metrics
    print(
        f"MISS spec={m.get('spec')} total={m['total_ms']:.1f}ms "
        f"orch={m.get('orchestration_overhead_ms', 0):.1f}ms "
        f"out={miss.output!r}"
    )


if __name__ == "__main__":
    main()
