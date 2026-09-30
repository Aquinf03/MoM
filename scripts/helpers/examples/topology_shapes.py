#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

"""Many shapes from one catalog — pick by name or heuristic."""
from __future__ import annotations
from models import register_builtins
from mom import (
    GraphRegistry,
    ModelDirectory,
    StateStore,
    register_builtin_shapes,
    run_named,
)
def main() -> None:
    directory = ModelDirectory()
    register_builtins(directory)
    registry = register_builtin_shapes(GraphRegistry(), directory)
    print("shapes:")
    for spec in registry.available(directory):
        hide = "hideable" if spec.latency_hideable else "visible-seam"
        print(f"  {spec.name:20} {spec.shape:16} {hide:14} {spec.description}")
    demos = [
        ("speculate_chat", "hi"),
        ("fanout_reconcile", "merge views please"),
        ("pipeline_transform", "reverse this"),
        (None, "hello"),  # heuristic
        (None, {"image": "img://cat"}),
    ]
    for name, prompt in demos:
        r = run_named(name, prompt, directory, registry, state=StateStore())
        print(
            f"\n[{r.metrics.get('graph')}] hideable={r.metrics.get('latency_hideable')} "
            f"total={r.metrics.get('total_ms', 0):.1f}ms → {r.output!r}"
        )
if __name__ == "__main__":
    main()
