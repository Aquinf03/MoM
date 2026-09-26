#!/usr/bin/env python3
"""
Prove: new model = drop into models/ + wire a Graph; zero runtime rewrite.

This example only touches `models/stub_shout.py` (already seeded) and graph
wiring below — it does not import or patch mom-core / scheduler internals.

  python examples/add_a_model.py
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
    register_builtins(directory)

    assert "stub.shout" in directory, "stub.shout missing — add models/stub_shout.py to _SEED"

    # Wire by id only. No changes under crates/ or python/mom/ required.
    graph = (
        Graph()
        .add("classify", "stub.classifier")
        .add("yell", "stub.shout")
        .link("classify", "yell")
    )
    print(f"plan: {plan_graph(graph)}")
    result = run(graph, "drop-in works", directory, state=StateStore())
    st = result.state
    print(f"output: {result.output}")
    print(f"trace:  {st.get('trace') if st else None}")
    print("touched core? no — models/stub_shout.py + this Graph wiring only")


if __name__ == "__main__":
    main()
