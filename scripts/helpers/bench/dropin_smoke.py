#!/usr/bin/env python3
"""
Drop-in model gate: register + graph wire without editing runtime packages.

  python scripts/helpers/bench/dropin_smoke.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from models import register_builtins
from mom import Graph, ModelDirectory, StateStore, run

FORBIDDEN_IMPORT_PREFIXES = (
    "mom._native",
    "mom.scheduler",
    "mom.graph",
    "crates",
)


def _imports_of(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def main() -> None:
    shout_path = ROOT / "src" / "models" / "stub_shout.py"
    assert shout_path.is_file(), shout_path

    imports = _imports_of(shout_path)
    bad = [
        i
        for i in imports
        if any(i == p or i.startswith(p + ".") for p in FORBIDDEN_IMPORT_PREFIXES)
    ]
    core_clean = not bad

    directory = ModelDirectory()
    register_builtins(directory)
    registered = "stub.shout" in directory

    graph = (
        Graph()
        .add("classify", "stub.classifier")
        .add("yell", "stub.shout")
        .link("classify", "yell")
    )
    result = run(graph, "drop-in", directory, state=StateStore())
    out_ok = (
        isinstance(result.output, dict)
        and result.output.get("model") == "stub.shout"
        and "DROP-IN" in str(result.output.get("text", ""))
    )

    print(f"stub_shout imports: {imports}")
    print(f"forbidden imports: {bad or 'none'}")
    print(f"output: {result.output}")

    checks = [
        ("model file avoids runtime internals", core_clean),
        ("registered in directory", registered),
        ("graph run uses shout by id", out_ok),
    ]
    for label, ok in checks:
        print(f"{label}: {'PASS' if ok else 'FAIL'}")
    overall = all(ok for _, ok in checks)
    print(f"overall: {'PASS' if overall else 'FAIL'}")
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
