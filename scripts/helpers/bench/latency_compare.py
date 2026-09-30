#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

"""
Latency harness: single-model baseline vs MoM speculate pipeline.
Uses stub delays (deterministic-ish) so you can validate orchestration
overhead and speculation hit/miss without real weights.
  python bench/latency_compare.py
  python bench/latency_compare.py --rounds 50 --warmup 5
"""
from __future__ import annotations
import argparse
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from models import register_builtins
from mom import Graph, ModelDirectory, StateStore, run
def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)
@dataclass
class Series:
    name: str
    totals_ms: list[float] = field(default_factory=list)
    orch_ms: list[float] = field(default_factory=list)
    router_ms: list[float] = field(default_factory=list)
    model_ms: list[float] = field(default_factory=list)
    hits: int = 0
    misses: int = 0
    def add(self, metrics: dict[str, Any], *, spec: str | None = None) -> None:
        self.totals_ms.append(float(metrics.get("total_ms", 0.0)))
        self.orch_ms.append(float(metrics.get("orchestration_overhead_ms", 0.0)))
        self.router_ms.append(float(metrics.get("router_ms", 0.0)))
        self.model_ms.append(float(metrics.get("model_ms", 0.0)))
        if spec == "hit":
            self.hits += 1
        elif spec == "miss":
            self.misses += 1
    def summary(self) -> dict[str, Any]:
        t = sorted(self.totals_ms)
        o = sorted(self.orch_ms)
        n = len(t)
        spec_n = self.hits + self.misses
        return {
            "name": self.name,
            "n": n,
            "total_p50": _percentile(t, 50),
            "total_p95": _percentile(t, 95),
            "total_mean": statistics.fmean(t) if t else 0.0,
            "total_stdev": statistics.stdev(t) if n > 1 else 0.0,
            "orch_p50": _percentile(o, 50),
            "orch_p95": _percentile(o, 95),
            "orch_mean": statistics.fmean(o) if o else 0.0,
            "router_mean": statistics.fmean(self.router_ms) if self.router_ms else 0.0,
            "model_mean": statistics.fmean(self.model_ms) if self.model_ms else 0.0,
            "hit_rate": (self.hits / spec_n) if spec_n else None,
            "hits": self.hits,
            "misses": self.misses,
        }
def _time_call(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Run fn; ensure total_ms exists (baseline may only have wall clock)."""
    t0 = time.perf_counter()
    metrics = fn()
    wall = (time.perf_counter() - t0) * 1000.0
    if "total_ms" not in metrics:
        metrics = {**metrics, "total_ms": wall}
    return metrics
def baseline_slm(directory: ModelDirectory, prompt: str) -> dict[str, Any]:
    """Single-model path: just stub.slm (no router, no graph)."""
    state = StateStore()
    model = directory.create("stub.slm")
    t0 = time.perf_counter()
    _ = model.run(prompt, state)
    total = (time.perf_counter() - t0) * 1000.0
    return {
        "total_ms": total,
        "orchestration_overhead_ms": 0.0,
        "router_ms": 0.0,
        "model_ms": total,
    }
def mom_hit(directory: ModelDirectory, graph: Graph, prompt: str) -> dict[str, Any]:
    state = StateStore()
    # easy → decision routes to stub.slm (matches prior)
    result = run(graph, prompt, directory, state=state)
    m = dict(result.metrics)
    spec = (m.get("spec") or {}).get("router")
    m["_spec"] = spec
    return m
def mom_miss(directory: ModelDirectory, graph: Graph, prompt: str) -> dict[str, Any]:
    state = StateStore()
    state.set("classification", "hard")
    result = run(graph, prompt, directory, state=state)
    m = dict(result.metrics)
    spec = (m.get("spec") or {}).get("router")
    m["_spec"] = spec
    return m
def _print_row(label: str, s: dict[str, Any]) -> None:
    hit = ""
    if s.get("hit_rate") is not None:
        hit = f"  hit_rate={s['hit_rate']*100:.0f}% ({s['hits']}/{s['hits']+s['misses']})"
    print(
        f"{label:18} n={s['n']:3}  "
        f"p50={s['total_p50']:6.1f}ms  p95={s['total_p95']:6.1f}ms  "
        f"mean={s['total_mean']:6.1f}±{s['total_stdev']:5.1f}  "
        f"orch_p50={s['orch_p50']:5.2f}ms  orch_p95={s['orch_p95']:5.2f}ms"
        f"{hit}"
    )
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=30, help="timed rounds per series")
    parser.add_argument("--warmup", type=int, default=3, help="warmup rounds (discarded)")
    parser.add_argument(
        "--hit-prompt",
        default="hi",
        help="prompt that should speculate-hit (easy → SLM)",
    )
    parser.add_argument(
        "--miss-prompt",
        default="please reason carefully about this",
        help="prompt used with forced hard classification",
    )
    args = parser.parse_args()
    directory = ModelDirectory()
    register_builtins(directory)
    graph = (
        Graph()
        .add("router", "stub.decision")
        .add("fast", "stub.slm")
        .speculate("router", "fast")
    )
    series = {
        "baseline_slm": Series("baseline_slm"),
        "mom_hit": Series("mom_hit"),
        "mom_miss": Series("mom_miss"),
    }
    runners: dict[str, Callable[[], dict[str, Any]]] = {
        "baseline_slm": lambda: baseline_slm(directory, args.hit_prompt),
        "mom_hit": lambda: mom_hit(directory, graph, args.hit_prompt),
        "mom_miss": lambda: mom_miss(directory, graph, args.miss_prompt),
    }
    print(f"warmup={args.warmup} rounds={args.rounds}")
    print(f"graph: decision → speculate(stub.slm)")
    print()
    for name, fn in runners.items():
        for _ in range(args.warmup):
            _time_call(fn)
        for _ in range(args.rounds):
            metrics = _time_call(fn)
            spec = metrics.pop("_spec", None)
            series[name].add(metrics, spec=spec)
    summaries = {k: v.summary() for k, v in series.items()}
    print("=== totals ===")
    for key in ("baseline_slm", "mom_hit", "mom_miss"):
        _print_row(key, summaries[key])
    base = summaries["baseline_slm"]
    hit = summaries["mom_hit"]
    miss = summaries["mom_miss"]
    # Miss penalty vs hit (extra work when speculation is wrong)
    miss_penalty = miss["total_p50"] - hit["total_p50"]
    # Hit overhead vs single SLM (should be small if speculation hides the router)
    hit_overhead = hit["total_p50"] - base["total_p50"]
    # Model variance proxy: stdev of baseline totals
    variance = base["total_stdev"]
    orch = hit["orch_p50"]
    print()
    print("=== derived ===")
    print(f"hit_overhead_vs_baseline_p50 = {hit_overhead:+.1f}ms")
    print(f"miss_penalty_vs_hit_p50      = {miss_penalty:+.1f}ms")
    print(f"baseline_stdev (variance)    = {variance:.2f}ms")
    print(f"mom_hit orch_p50             = {orch:.2f}ms")
    # Pass: orchestration ≪ natural model variance (or absolute tiny if variance~0 on stubs)
    print()
    print("=== pass criteria ===")
    if variance > 1.0:
        ok = orch < 0.5 * variance
        print(
            f"orch_p50 ({orch:.2f}ms) ≪ 0.5×baseline_stdev ({0.5*variance:.2f}ms): "
            f"{'PASS' if ok else 'FAIL'}"
        )
    else:
        # Stub sleeps are stable → variance near zero; use absolute budget instead
        ok = orch < 5.0
        print(
            f"baseline_stdev≈0 on stubs; orch_p50 ({orch:.2f}ms) < 5ms absolute: "
            f"{'PASS' if ok else 'FAIL'}"
        )
    hit_ok = hit_overhead < 25.0  # router overlapped; allow a little slack on stubs
    print(
        f"hit_overhead_vs_baseline_p50 ({hit_overhead:+.1f}ms) < 25ms: "
        f"{'PASS' if hit_ok else 'FAIL'}"
    )
    miss_ok = miss_penalty > 20.0  # should clearly pay for discarded prior + LLM
    print(
        f"miss_penalty_vs_hit_p50 ({miss_penalty:+.1f}ms) > 20ms (visible miss): "
        f"{'PASS' if miss_ok else 'FAIL'}"
    )
    all_ok = ok and hit_ok and miss_ok
    print()
    print(f"overall: {'PASS' if all_ok else 'FAIL'}")
    raise SystemExit(0 if all_ok else 1)
if __name__ == "__main__":
    main()
