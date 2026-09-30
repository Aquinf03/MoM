#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

"""
Wide catalog gate: many kinds, one Model contract.
  python bench/catalog_smoke.py
"""
from __future__ import annotations
from models import catalog_ids, register_builtins
from mom import ModelDirectory
from mom.adapter import Model
# Minimum span we call "wide" for v1 (stubs stand in for real weights).
REQUIRED_MODALITIES = {
    "text",
    "embedding",
    "vision",
    "audio",
    "retrieval",
    "tool",
    "code",
}
MIN_IDS = 20
def main() -> None:
    directory = ModelDirectory()
    register_builtins(directory)
    ids = catalog_ids()
    modalities: set[str] = set()
    protocol_ok = 0
    kinds: set[str] = set()
    for mid in ids:
        entry = directory.get(mid)
        mod = entry.meta.get("modality")
        if isinstance(mod, str):
            modalities.add(mod)
        kinds.update(entry.tags)
        inst = directory.create(mid)
        if isinstance(inst, Model):
            protocol_ok += 1
    print(f"catalog ids ({len(ids)}): {ids}")
    print(f"modalities: {sorted(modalities)}")
    print(f"protocol Model satisfied: {protocol_ok}/{len(ids)}")
    wide = len(ids) >= MIN_IDS
    mods_ok = REQUIRED_MODALITIES.issubset(modalities)
    all_proto = protocol_ok == len(ids)
    # Generators + routers + transforms represented
    span_ok = {"generator", "router", "embedder", "vision", "tool"} <= kinds
    checks = [
        (f"≥{MIN_IDS} registered ids", wide),
        ("required modalities present", mods_ok),
        ("all entries satisfy Model protocol", all_proto),
        ("tag span covers core kinds", span_ok),
    ]
    for label, ok in checks:
        print(f"{label}: {'PASS' if ok else 'FAIL'}")
    overall = all(ok for _, ok in checks)
    print(f"overall: {'PASS' if overall else 'FAIL'}")
    raise SystemExit(0 if overall else 1)
if __name__ == "__main__":
    main()
