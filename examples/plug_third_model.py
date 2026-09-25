#!/usr/bin/env python3
"""
Plug a third unrelated model into a *different* graph — zero core changes.

Chat path (elsewhere):  decision → speculate(slm)
This path:              classifier → reverse   (unrelated transform pipeline)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "python"), str(ROOT)]

from models import register_builtins
from mom import Graph, ModelDirectory, StateStore, plan_graph, run


def main() -> None:
    directory = ModelDirectory()
    register_builtins(directory)  # includes stub.reverse via models/_SEED

    # Different topology from chat speculate — no mom-core / scheduler edits.
    graph = (
        Graph()
        .add("classify", "stub.classifier")
        .add("flip", "stub.reverse")
        .link("classify", "flip")
    )

    print(f"plan: {plan_graph(graph)}")
    print(f"plugged model ids: stub.classifier, stub.reverse")

    state = StateStore()
    result = run(graph, "MoM plugs models", directory, state=state)
    # Use result.state — native hops write through the returned handle.
    st = result.state or state

    print(f"output: {result.output}")
    print(f"trace:  {st.get('trace')}")
    print(f"label:  {st.get('classification')}")
    print(
        "core touched? no — only models/stub_reverse.py + this graph wiring"
    )


if __name__ == "__main__":
    main()
