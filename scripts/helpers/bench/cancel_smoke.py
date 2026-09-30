#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

"""
Cancel speculative losers: on miss, prior should stop early (not run full delay).
  python bench/cancel_smoke.py
"""
from __future__ import annotations
import time
from models import register_builtins
from models.stub_slm import SlmModel
from mom import CancelToken, CancelledError, Graph, ModelDirectory, StateStore, run
def main() -> None:
    # Unit: token interrupts long sleep
    token = CancelToken()
    model = SlmModel(delay_ms=500.0)
    state = StateStore()
    def worker() -> None:
        try:
            model.run("x", state, cancel=token)
        except CancelledError:
            return
        raise AssertionError("expected CancelledError")
    import threading
    t = threading.Thread(target=worker)
    t0 = time.perf_counter()
    t.start()
    time.sleep(0.03)
    token.cancel()
    t.join(timeout=2.0)
    elapsed = (time.perf_counter() - t0) * 1000.0
    unit_ok = elapsed < 200.0 and not t.is_alive()
    print(f"unit cancel during 500ms sleep: {elapsed:.1f}ms  [{'PASS' if unit_ok else 'FAIL'}]")
    # Integration: MoM miss should cancel prior SLM (~30ms) early when possible
    directory = ModelDirectory()
    register_builtins(directory)
    graph = (
        Graph()
        .add("router", "stub.decision")
        .add("fast", "stub.slm")
        .speculate("router", "fast")
    )
    # Make prior slow so cancel is observable
    directory._entries["stub.slm"].factory = lambda: SlmModel(delay_ms=200.0)  # type: ignore[attr-defined]
    # Re-mirror native callable
    if directory.native is not None:
        def _call(inp, st, cancel=None):
            return SlmModel(delay_ms=200.0).run(inp, st, cancel=cancel)
        # overwrite registration by using a fresh directory for native
        from mom._native import ModelDirectory as NativeDir
        native = NativeDir()
        for eid in directory.ids():
            entry = directory.get(eid)
            if eid == "stub.slm":
                native.register(eid, _call, tags=sorted(entry.tags))
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
    st = StateStore()
    st.set("classification", "hard")
    t0 = time.perf_counter()
    result = run(graph, "please reason carefully", directory, state=st)
    wall = (time.perf_counter() - t0) * 1000.0
    m = result.metrics
    spec = (m.get("spec") or {}).get("router")
    cancelled = bool(m.get("prior_cancelled"))
    prior_ms = float(m.get("prior_cancelled_ms") or m.get("node_ms", {}).get("fast", 999))
    # Router ~15ms + LLM ~80ms ≈ 95ms; without cancel prior adds up to +200ms overlap waste
    # With cancel, prior_ms should be well under 200ms full sleep.
    integ_ok = (
        spec == "miss"
        and cancelled
        and prior_ms < 120.0
        and wall < 250.0
    )
    print(
        f"mom miss cancel: spec={spec} cancelled={cancelled} "
        f"prior_ms={prior_ms:.1f} wall={wall:.1f}ms  "
        f"[{'PASS' if integ_ok else 'FAIL'}]"
    )
    print(f"overall: {'PASS' if unit_ok and integ_ok else 'FAIL'}")
    raise SystemExit(0 if unit_ok and integ_ok else 1)
if __name__ == "__main__":
    main()
