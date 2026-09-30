#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

"""Catalog span + optional embedding-bus hop (measure-only prototype)."""
from __future__ import annotations
from models import catalog_ids, register_builtins
from mom import Bus, Graph, ModelDirectory, StateStore, run
def main() -> None:
    directory = ModelDirectory()
    register_builtins(directory)
    ids = catalog_ids()
    print(f"catalog ({len(ids)}):")
    for i in ids:
        print(f"  {i}")
    # Composition stays graph + directory ids — vision path, no core changes.
    vision = Graph().add("cap", "stub.vision.local")
    print("vision:", run(vision, {"image": "img://demo"}, directory).output)
    # Optional embedding bus on embed→similarity (not mandated).
    emb_graph = (
        Graph()
        .add("embed", "stub.embedder.raw")
        .add("score", "stub.similarity")
        .link("embed", "score")
    )
    result = run(
        emb_graph,
        "beta",
        directory,
        state=StateStore(),
        bus=Bus.embedding(),
    )
    print(
        f"embedding hop: best={result.output.get('best')} "
        f"bus_ms={result.metrics.get('bus_ms', 0):.3f} "
        f"hops={result.metrics.get('bus_hops')}"
    )
if __name__ == "__main__":
    main()
