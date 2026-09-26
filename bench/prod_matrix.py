#!/usr/bin/env python3
"""
Production-grade SDK matrix — run against the *installed* mom package.

  maturin develop   # or pip install -e python/
  pytest -q
  python bench/prod_matrix.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    # Prove imports come from site-packages / venv install, not only source tree hacks
    import mom

    print(f"mom {mom.__version__} native={mom.NATIVE} file={mom.__file__}")
    print(f"ping={mom.ping()!r}")

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        str(ROOT / "tests"),
        "--tb=line",
    ]
    print("running:", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    # Extra: CLI entry
    ping = subprocess.run(
        [sys.executable, "-m", "mom"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    print(ping.stdout.strip() or ping.stderr.strip())
    if ping.returncode != 0:
        raise SystemExit(ping.returncode)

    print("prod matrix: PASS")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
