#!/usr/bin/env python3
"""Minimal wiring: catalog → shared StateStore → model hop."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "python"), str(ROOT)]

from models import register_builtins
from mom import Graph, ModelDirectory, StateStore, ping


def main() -> None:
    directory = ModelDirectory()
    register_builtins(directory)

    graph = Graph().add("gen", "stub.echo")
    state = StateStore()
    state.set("session", "demo")

    model = directory.create("stub.echo")
    out = model.run("hello from mom", state)

    print(f"native ping: {ping()}")
    print(f"directory: {directory.ids()}")
    print(f"graph nodes: {[(n.name, n.model_id) for n in graph.nodes]}")
    print(f"output: {out!r}")
    print(f"state: {state.snapshot()}")


if __name__ == "__main__":
    main()
