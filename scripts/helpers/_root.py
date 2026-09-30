"""Repo root + sys.path bootstrap for scripts under scripts/helpers/."""

from __future__ import annotations

import sys
from pathlib import Path

# scripts/helpers/_root.py → parents[2] = repo root
REPO_ROOT = Path(__file__).resolve().parents[2]


def boot(extra: list[Path] | None = None) -> Path:
    """Put `src/` (and repo root for `models` package) on sys.path."""
    paths = [REPO_ROOT / "src", REPO_ROOT]
    if extra:
        paths.extend(extra)
    sys.path[:0] = [str(p) for p in paths]
    return REPO_ROOT
