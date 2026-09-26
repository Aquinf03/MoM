#!/usr/bin/env python3
"""
Optional embedding bus on one hop — measure, don't mandate.

Compares text/JSON vs embedding packing for the embed→similarity hop,
and runs a tiny graph with Bus.embedding() on that path.

  python bench/embedding_bus_smoke.py
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "python"), str(ROOT)]

from models import register_builtins
from models.stub_embedder import _pseudo_embedding
from mom import Bus, Graph, ModelDirectory, Scheduler, StateStore


def _bench_roundtrip(bus: Bus, value, n: int = 2000) -> float:
    # Warm
    for _ in range(50):
        bus.roundtrip(value)
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        bus.roundtrip(value)
        times.append((time.perf_counter() - t0) * 1e6)  # µs
    return statistics.median(times)


def main() -> None:
    dims = 256
    vec = _pseudo_embedding("measure me", dims)
    text_payload = {"embedding": vec, "dims": dims, "model": "stub.embedder"}

    text_bus = Bus.text_json()
    emb_bus = Bus.embedding()

    text_us = _bench_roundtrip(text_bus, text_payload)
    emb_us = _bench_roundtrip(emb_bus, vec)
    # Also pack the same numbers as JSON array for fair-ish compare
    json_arr_us = _bench_roundtrip(text_bus, vec)

    print(f"dims={dims}  median roundtrip:")
    print(f"  text_json(dict envelope): {text_us:.2f} µs")
    print(f"  text_json(float array):   {json_arr_us:.2f} µs")
    print(f"  embedding(f32 LE):        {emb_us:.2f} µs")
    ratio = json_arr_us / emb_us if emb_us > 0 else float("inf")
    print(f"  embedding vs json-array:  {ratio:.1f}x")

    directory = ModelDirectory()
    register_builtins(directory)
    graph = (
        Graph()
        .add("embed", "stub.embedder.raw")
        .add("score", "stub.similarity")
        .link("embed", "score")
    )

    # Text bus path (dict/list via JSON)
    text_sched = Scheduler(directory, bus=Bus.text_json())
    # Force raw list through text bus — works (JSON array)
    r_text = text_sched.run(graph, "alpha", StateStore())
    # Embedding bus path — packs the vector hop only
    emb_sched = Scheduler(directory, bus=Bus.embedding())
    r_emb = emb_sched.run(graph, "alpha", StateStore())

    print(
        f"graph text bus:  best={r_text.output.get('best') if isinstance(r_text.output, dict) else r_text.output} "
        f"bus_ms={r_text.metrics.get('bus_ms', 0):.3f} hops={r_text.metrics.get('bus_hops', 0)}"
    )
    print(
        f"graph emb bus:   best={r_emb.output.get('best') if isinstance(r_emb.output, dict) else r_emb.output} "
        f"bus_ms={r_emb.metrics.get('bus_ms', 0):.3f} hops={r_emb.metrics.get('bus_hops', 0)} "
        f"kind={r_emb.metrics.get('bus_kind')}"
    )

    same = (
        isinstance(r_text.output, dict)
        and isinstance(r_emb.output, dict)
        and r_text.output.get("best") == r_emb.output.get("best")
    )
    packed = int(r_emb.metrics.get("bus_hops") or 0) >= 1
    faster_or_ok = emb_us <= json_arr_us * 1.5  # embedding should not be wildly worse
    overall = same and packed and faster_or_ok
    print(f"same graph result:     {'PASS' if same else 'FAIL'}")
    print(f"embedding hop packed:  {'PASS' if packed else 'FAIL'}")
    print(f"packing competitive:   {'PASS' if faster_or_ok else 'FAIL'}")
    print(f"overall: {'PASS' if overall else 'FAIL'}")
    print("(text bus remains the default; embedding is optional per hop/graph)")
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
