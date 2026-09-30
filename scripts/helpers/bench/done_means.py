#!/usr/bin/env python3
"""
§10 done-means gates (pre-SDK): wide catalog, drop-in model, speculation proof.

  python scripts/helpers/bench/done_means.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

PY = sys.executable
HELPERS = Path("scripts/helpers")

GATES = (
    ("wide catalog (one contract)", [str(HELPERS / "bench/catalog_smoke.py")]),
    ("drop-in model, no runtime rewrite", [str(HELPERS / "bench/dropin_smoke.py")]),
    (
        "speculate vs single-model baseline",
        [str(HELPERS / "bench/latency_compare.py"), "--rounds", "20", "--warmup", "2"],
    ),
    ("one-command colocated demo", [str(HELPERS / "examples/hello_mom.py")]),
)


def main() -> None:
    results: list[tuple[str, bool]] = []
    for label, argv in GATES:
        print(f"\n======== {label} ========")
        proc = subprocess.run([PY, *argv], cwd=ROOT)
        ok = proc.returncode == 0
        results.append((label, ok))
        print(f"→ {label}: {'PASS' if ok else 'FAIL'}")

    print("\n======== summary ========")
    for label, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {label}")
    overall = all(ok for _, ok in results)
    print(f"overall: {'PASS' if overall else 'FAIL'}")
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
