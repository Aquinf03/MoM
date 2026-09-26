#!/usr/bin/env python3
"""
Backpressure / concurrency limits smoke.

  python bench/limits_smoke.py
"""

from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "python"), str(ROOT)]

from models import register_builtins
from models.stub_slm import SlmModel
from mom import (
    ConcurrencyLimits,
    Graph,
    LimitExceeded,
    Limiter,
    ModelDirectory,
    Scheduler,
    StateStore,
)


def main() -> None:
    directory = ModelDirectory()
    register_builtins(directory)
    # Slow SLM so overlapping runs are easy to observe
    directory._entries["stub.slm"].factory = lambda: SlmModel(delay_ms=80.0)  # type: ignore[attr-defined]
    if directory.native is not None:
        from mom._native import ModelDirectory as NativeDir

        native = NativeDir()

        def slow_slm(inp, st, cancel=None):
            return SlmModel(delay_ms=80.0).run(inp, st, cancel=cancel)

        for eid in directory.ids():
            entry = directory.get(eid)
            if eid == "stub.slm":
                native.register(eid, slow_slm, tags=sorted(entry.tags))
            else:

                def make(f=entry.factory):
                    def call(inp, st, cancel=None, _f=f):
                        try:
                            return _f().run(inp, st, cancel=cancel)
                        except TypeError:
                            return _f().run(inp, st)

                    return call

                native.register(eid, make(), tags=sorted(entry.tags))
        directory._native = native  # type: ignore[attr-defined]

    graph = Graph().add("gen", "stub.slm")
    limiter = Limiter(ConcurrencyLimits(max_runs=2, max_model_workers=4, acquire_timeout_s=0.05))
    sched = Scheduler(directory, limits=limiter)

    peak_runs = 0
    lock = threading.Lock()
    rejected = 0
    ok = 0

    def one(_: int) -> str:
        nonlocal peak_runs, rejected, ok
        try:
            with lock:
                # sample peak just before/during — limiter updates inside run
                pass
            result = sched.run(graph, "hi", StateStore())
            with lock:
                peak_runs = max(peak_runs, int(result.metrics.get("limits", {}).get("runs_active", 0)))
                # Also track live peak via limiter during wait windows
                peak_runs = max(peak_runs, limiter.runs_active)
                ok += 1
            return "ok"
        except LimitExceeded:
            with lock:
                rejected += 1
            return "rejected"

    # Hammer with more workers than max_runs
    n = 12
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = [pool.submit(one, i) for i in range(n)]
        # Sample peak while running
        while any(not f.done() for f in futs):
            with lock:
                peak_runs = max(peak_runs, limiter.runs_active)
            time.sleep(0.005)
        for f in as_completed(futs):
            f.result()
    wall = (time.perf_counter() - t0) * 1000.0

    snap = limiter.snapshot()
    print(f"submitted={n} ok={ok} rejected={rejected} wall={wall:.0f}ms")
    print(f"peak_runs_observed={peak_runs} max_runs={limiter.limits.max_runs}")
    print(f"limiter snapshot: {snap}")

    # Must never exceed max_runs; with timeout 0.05 some should reject under load
    capped = peak_runs <= limiter.limits.max_runs
    some_rejected = rejected > 0
    some_ok = ok > 0
    overall = capped and some_rejected and some_ok
    print(f"capped at max_runs:     {'PASS' if capped else 'FAIL'}")
    print(f"backpressure rejects:   {'PASS' if some_rejected else 'FAIL'}")
    print(f"some runs succeeded:    {'PASS' if some_ok else 'FAIL'}")
    print(f"overall: {'PASS' if overall else 'FAIL'}")
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
