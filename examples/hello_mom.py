#!/usr/bin/env python3
"""Minimal wiring: catalog → graph (execution via mom-core comes next)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "python"), str(ROOT)]

from models import register_builtins
from mom import Graph, ModelDirectory


def main() -> None:
    directory = ModelDirectory()
    register_builtins(directory)

    graph = (
        Graph()
        .add("gen", "stub.echo")
    )

    model = directory.create("stub.echo")
    state: dict = {}
    out = model.run("hello from mom", state)

    print(f"directory: {directory.ids()}")
    print(f"graph nodes: {[(n.name, n.model_id) for n in graph.nodes]}")
    print(f"output: {out!r}")
    print(f"trace: {state.get('trace')}")


if __name__ == "__main__":
    main()
