#!/usr/bin/env python3
"""
Hot-path profile: bus serialization vs shared StateStore, plus network audit.

- Times text-bus encode/decode vs StateStore get/set for the same payload
- Runs a MoM graph under a socket.connect ban (fail if any network hop)
- Reports bus span ms from Trace metrics

  python bench/hot_path_profile.py
"""

from __future__ import annotations

import socket
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "python"), str(ROOT)]

from models import register_builtins
from mom import Bus, Graph, ModelDirectory, StateStore, run


class NetworkHopError(RuntimeError):
    """Raised if the hot path attempts a network connect."""


def _ban_network() -> Any:
    """Patch socket.socket.connect to forbid outbound connects during the run."""
    real_connect = socket.socket.connect

    def blocked(self: socket.socket, address: Any) -> None:  # noqa: ANN401
        raise NetworkHopError(
            f"accidental network hop in hot path: connect({address!r})"
        )

    socket.socket.connect = blocked  # type: ignore[method-assign]
    return real_connect


def _restore_network(real_connect: Any) -> None:
    socket.socket.connect = real_connect  # type: ignore[method-assign]


def _time_ms(fn: Any, rounds: int) -> list[float]:
    samples: list[float] = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


def profile_bus_vs_state(*, rounds: int = 200) -> dict[str, float]:
    bus = Bus.text_json()
    store = StateStore()
    payload = {
        "role": "user",
        "text": "MoM shared state vs serialized hop " * 8,
        "meta": {"n": 42, "tags": ["a", "b", "c"]},
    }

    def ser() -> None:
        p = bus.encode(payload)
        _ = bus.decode(p)

    def state_roundtrip() -> None:
        store.set("hop", payload)
        _ = store.get("hop")

    # warmup
    for _ in range(20):
        ser()
        state_roundtrip()

    ser_ms = _time_ms(ser, rounds)
    st_ms = _time_ms(state_roundtrip, rounds)
    return {
        "bus_encode_decode_p50_ms": statistics.median(ser_ms),
        "bus_encode_decode_mean_ms": statistics.fmean(ser_ms),
        "state_set_get_p50_ms": statistics.median(st_ms),
        "state_set_get_mean_ms": statistics.fmean(st_ms),
    }


def profile_mom_bus_spans(directory: ModelDirectory, rounds: int = 20) -> dict[str, float]:
    graph = (
        Graph()
        .add("router", "stub.decision")
        .add("fast", "stub.slm")
        .speculate("router", "fast")
    )
    bus_totals: list[float] = []
    orch: list[float] = []
    for _ in range(rounds):
        result = run(graph, "hi", directory, state=StateStore())
        spans = result.metrics.get("spans") or []
        bus_ms = sum(
            float(s.get("duration_ms", 0.0))
            for s in spans
            if s.get("kind") == "bus"
        )
        bus_totals.append(bus_ms)
        orch.append(float(result.metrics.get("orchestration_overhead_ms", 0.0)))
    return {
        "mom_bus_spans_p50_ms": statistics.median(bus_totals),
        "mom_bus_spans_mean_ms": statistics.fmean(bus_totals),
        "mom_orch_p50_ms": statistics.median(orch),
    }


def audit_no_network(directory: ModelDirectory) -> None:
    graph = (
        Graph()
        .add("router", "stub.decision")
        .add("fast", "stub.slm")
        .speculate("router", "fast")
    )
    real = _ban_network()
    try:
        run(graph, "hi", directory, state=StateStore())
        # also miss path
        st = StateStore()
        st.set("classification", "hard")
        run(graph, "please reason carefully", directory, state=st)
    finally:
        _restore_network(real)


def static_scan_for_network_imports() -> list[str]:
    """Flag obvious network client imports under models/ and python/mom/."""
    banned = (
        "import requests",
        "from requests",
        "import httpx",
        "from httpx",
        "import urllib.request",
        "from urllib.request",
        "import aiohttp",
        "from aiohttp",
        "openai.OpenAI",
        "anthropic.Anthropic",
    )
    hits: list[str] = []
    roots = [ROOT / "models", ROOT / "python" / "mom"]
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for needle in banned:
                if needle in text:
                    hits.append(f"{path.relative_to(ROOT)}: {needle}")
    return hits


def main() -> None:
    directory = ModelDirectory()
    register_builtins(directory)

    print("=== static: no network clients in hot packages ===")
    static_hits = static_scan_for_network_imports()
    if static_hits:
        for h in static_hits:
            print(f"  FAIL  {h}")
        static_ok = False
    else:
        print("  PASS  no banned network imports in models/ or python/mom/")
        static_ok = True

    print()
    print("=== runtime: socket.connect banned during MoM run ===")
    try:
        audit_no_network(directory)
        print("  PASS  no connect() during hit+miss runs")
        net_ok = True
    except NetworkHopError as e:
        print(f"  FAIL  {e}")
        net_ok = False

    print()
    print("=== profile: bus serialize vs StateStore ===")
    prof = profile_bus_vs_state()
    for k, v in prof.items():
        print(f"  {k}: {v:.4f}ms")
    ratio = (
        prof["bus_encode_decode_p50_ms"] / prof["state_set_get_p50_ms"]
        if prof["state_set_get_p50_ms"] > 0
        else float("inf")
    )
    print(f"  bus/state p50 ratio: {ratio:.1f}x")

    print()
    print("=== profile: bus spans inside MoM Trace ===")
    mom = profile_mom_bus_spans(directory)
    for k, v in mom.items():
        print(f"  {k}: {v:.4f}ms")

    # Gate: shared-state path stays available; bus cost should not dominate stub model work (~30ms)
    bus_ok = mom["mom_bus_spans_p50_ms"] < 5.0
    print()
    print("=== pass criteria ===")
    print(f"static no-network imports: {'PASS' if static_ok else 'FAIL'}")
    print(f"runtime no-connect:        {'PASS' if net_ok else 'FAIL'}")
    print(
        f"MoM bus spans p50 < 5ms:   {'PASS' if bus_ok else 'FAIL'} "
        f"({mom['mom_bus_spans_p50_ms']:.3f}ms)"
    )
    overall = static_ok and net_ok and bus_ok
    print(f"overall: {'PASS' if overall else 'FAIL'}")
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
