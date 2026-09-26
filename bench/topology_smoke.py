#!/usr/bin/env python3
"""
Topology flexibility: registry shapes, heuristic pick, fan-out waves.

  python bench/topology_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "python"), str(ROOT)]

from models import register_builtins
from mom import (
    GraphRegistry,
    ModelDirectory,
    StateStore,
    heuristic_select,
    register_builtin_shapes,
    run,
    run_named,
)


def main() -> None:
    directory = ModelDirectory()
    register_builtins(directory)
    registry = register_builtin_shapes(GraphRegistry(), directory)

    names = registry.available_names(directory)
    print(f"available graphs ({len(names)}): {names}")

    # Explicit pick
    spec = registry.pick(directory, "speculate_chat")
    assert spec.latency_hideable

    # Heuristic: chat → speculate; reconcile keyword → fanout; image → vision
    assert heuristic_select(registry, directory, "hi") == "speculate_chat"
    assert (
        heuristic_select(registry, directory, "please reconcile both models")
        == "fanout_reconcile"
    )
    assert (
        heuristic_select(registry, directory, {"image": "img://x"}) == "vision_caption"
    )

    # Fan-out wave: wall ~ max(slm, llm) + reconcile, not sum of generators
    fan = registry.get("fanout_reconcile")
    r = run(fan.graph, "fanout please", directory, state=StateStore())
    waves = r.metrics.get("waves") or []
    parallel = [w for w in waves if w.get("type") == "parallel"]
    node_ms = r.metrics.get("node_ms") or {}
    a_ms = float(node_ms.get("a", 0))
    b_ms = float(node_ms.get("b", 0))
    crit = float(r.metrics.get("critical_path_ms") or 0)
    # critical path should be well under a+b+merge if gens overlapped
    serial_floor = a_ms + b_ms
    overlapped = bool(parallel) and crit < serial_floor + 5.0
    print(
        f"fanout waves={waves} a={a_ms:.1f} b={b_ms:.1f} "
        f"crit={crit:.1f} out={r.output!r}"
    )

    # Auto select + run_named
    auto = run_named(None, "hi there", directory, registry, state=StateStore())
    print(f"auto graph={auto.metrics.get('graph')} shape={auto.metrics.get('shape')}")

    # Missing model → graph not available
    empty = ModelDirectory()
    assert registry.available_names(empty) == []

    checks = [
        ("registry populated", len(names) >= 5),
        ("heuristic chat", True),
        ("fan-out overlapped", overlapped),
        ("auto speculate_chat", auto.metrics.get("graph") == "speculate_chat"),
        ("reconcile output", isinstance(r.output, dict) and "reconciled" in str(r.output.get("text", ""))),
    ]
    for label, ok in checks:
        print(f"{label}: {'PASS' if ok else 'FAIL'}")
    overall = all(ok for _, ok in checks)
    print(f"overall: {'PASS' if overall else 'FAIL'}")
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
