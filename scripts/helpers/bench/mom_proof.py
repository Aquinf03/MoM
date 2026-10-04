#!/usr/bin/env python3
"""
MoM must beat baselines on a real local-model bench or this exits 1.

Arms
----
  always_fast   — only the small chat model
  always_strong — only the bigger chat model
  mom           — router ∥ speculate(fast); miss → strong

Win rules (all required)
------------------------
  1. Easy speed:   mom p50  <  always_strong p50
  2. Hard score:   mom accuracy  >  always_fast accuracy
  3. Mix time:     mom total wall  <  always_strong total wall
                   (easy-heavy set)
  4. Plumbing:     easy hits + hard misses + orch tiny

  python scripts/helpers/bench/mom_proof.py --rounds 2 --json results/mom_proof.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "scripts" / "helpers" / "bench")]

from eval_set import EVAL, gold_ok  # noqa: E402
from mom import StateStore, run  # noqa: E402
from mom.runtime import ID_CHAT_STRONG, build_directory, build_registry  # noqa: E402


def _percentile(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def _text(out: Any) -> str:
    if isinstance(out, dict):
        for k in ("text", "answer", "output"):
            if isinstance(out.get(k), str):
                return out[k]
        return str(out)
    return str(out)


def _correct(text: str, item: dict[str, Any]) -> bool:
    return gold_ok(text, item)


@dataclass
class Arm:
    name: str
    totals: list[float] = field(default_factory=list)
    orch: list[float] = field(default_factory=list)
    hits: int = 0
    misses: int = 0
    correct: int = 0
    n: int = 0
    easy_totals: list[float] = field(default_factory=list)
    hard_totals: list[float] = field(default_factory=list)
    easy_correct: int = 0
    easy_n: int = 0
    hard_correct: int = 0
    hard_n: int = 0
    rows: list[dict[str, Any]] = field(default_factory=list)

    def add(
        self,
        *,
        item: dict[str, Any],
        total_ms: float,
        orch_ms: float,
        text: str,
        spec: str | None,
    ) -> None:
        ok = _correct(text, item)
        diff = item["diff"]
        self.totals.append(total_ms)
        self.orch.append(orch_ms)
        self.n += 1
        if ok:
            self.correct += 1
        if spec == "hit":
            self.hits += 1
        elif spec == "miss":
            self.misses += 1
        if diff == "easy":
            self.easy_totals.append(total_ms)
            self.easy_n += 1
            if ok:
                self.easy_correct += 1
        else:
            self.hard_totals.append(total_ms)
            self.hard_n += 1
            if ok:
                self.hard_correct += 1
        self.rows.append(
            {
                "id": item["id"],
                "diff": diff,
                "ms": round(total_ms, 1),
                "ok": ok,
                "spec": spec,
                "pred": (text or "")[:160],
            }
        )

    def snap(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "n": self.n,
            "acc": (self.correct / self.n) if self.n else 0.0,
            "easy_acc": (self.easy_correct / self.easy_n) if self.easy_n else 0.0,
            "hard_acc": (self.hard_correct / self.hard_n) if self.hard_n else 0.0,
            "p50": _percentile(self.totals, 50),
            "easy_p50": _percentile(self.easy_totals, 50),
            "hard_p50": _percentile(self.hard_totals, 50),
            "total_wall_ms": sum(self.totals),
            "orch_p50": _percentile(self.orch, 50),
            "hits": self.hits,
            "misses": self.misses,
        }


def _run_graph(directory, graph, prompt: str) -> dict[str, Any]:
    state = StateStore()
    t0 = time.perf_counter()
    result = run(graph, prompt, directory, state=state)
    wall = (time.perf_counter() - t0) * 1000.0
    m = dict(result.metrics)
    spec = m.get("spec") or {}
    outcome = next(iter(spec.values()), None) if isinstance(spec, dict) else None
    return {
        "total_ms": float(m.get("total_ms") or wall),
        "orch_ms": float(m.get("orchestration_overhead_ms") or 0.0),
        "text": _text(result.output),
        "spec": outcome,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    print("loading real models…", flush=True)
    directory = build_directory()
    reg = build_registry(directory)
    g_mom = reg.get("speculate_chat").graph
    g_fast = reg.get("direct_fast").graph
    g_strong = reg.get("direct_strong").graph

    print("warmup…", flush=True)
    for _ in range(max(1, args.warmup)):
        _run_graph(directory, g_mom, "Say ok.")
        _run_graph(directory, g_fast, "Say ok.")
        _run_graph(directory, g_strong, "Say ok.")

    mom = Arm("mom")
    fast = Arm("always_fast")
    strong = Arm("always_strong")

    for r in range(args.rounds):
        for item in EVAL:
            p = item["prompt"]
            for arm, graph, is_mom in (
                (mom, g_mom, True),
                (fast, g_fast, False),
                (strong, g_strong, False),
            ):
                out = _run_graph(directory, graph, p)
                arm.add(
                    item=item,
                    total_ms=out["total_ms"],
                    orch_ms=out["orch_ms"],
                    text=out["text"],
                    spec=out["spec"] if is_mom else None,
                )
                tag = out["spec"] or "-"
                print(
                    f"[{arm.name:13}] r{r+1} {item['id']} {item['diff']:4} "
                    f"{tag:4} {out['total_ms']:7.1f}ms  "
                    f"{'OK' if _correct(out['text'], item) else 'NO'}",
                    flush=True,
                )

    m, f, s = mom.snap(), fast.snap(), strong.snap()

    easy_spec_n = sum(1 for row in mom.rows if row["diff"] == "easy")
    hard_spec_n = sum(1 for row in mom.rows if row["diff"] == "hard")
    easy_hits = sum(1 for row in mom.rows if row["diff"] == "easy" and row["spec"] == "hit")
    hard_misses = sum(1 for row in mom.rows if row["diff"] == "hard" and row["spec"] == "miss")

    checks = [
        (
            "beat always_strong on easy speed (p50)",
            m["easy_p50"] < s["easy_p50"],
            f"mom={m['easy_p50']:.1f}ms  strong={s['easy_p50']:.1f}ms",
        ),
        (
            "beat always_fast on hard accuracy",
            m["hard_acc"] > f["hard_acc"],
            f"mom={m['hard_acc']:.0%}  fast={f['hard_acc']:.0%}",
        ),
        (
            "beat always_strong on total wall time (mixed set)",
            m["total_wall_ms"] < s["total_wall_ms"],
            f"mom={m['total_wall_ms']:.0f}ms  strong={s['total_wall_ms']:.0f}ms",
        ),
        (
            "easy path actually hits fast",
            easy_hits == easy_spec_n and easy_spec_n > 0,
            f"{easy_hits}/{easy_spec_n} hits",
        ),
        (
            "hard path misses to strong",
            hard_misses == hard_spec_n and hard_spec_n > 0,
            f"{hard_misses}/{hard_spec_n} misses",
        ),
        (
            "orch not eating the win",
            m["orch_p50"] < 5.0,
            f"orch_p50={m['orch_p50']:.2f}ms",
        ),
    ]
    overall = all(ok for _, ok, _ in checks)

    print()
    print("======== SCOREBOARD ========")
    print(
        f"{'arm':13} {'acc':>6} {'easy_acc':>8} {'hard_acc':>8} "
        f"{'easy_p50':>9} {'total_ms':>10}"
    )
    for snap in (m, f, s):
        print(
            f"{snap['name']:13} {snap['acc']:6.0%} {snap['easy_acc']:8.0%} "
            f"{snap['hard_acc']:8.0%} {snap['easy_p50']:8.1f}ms "
            f"{snap['total_wall_ms']:9.0f}ms"
        )
    print()
    for name, ok, detail in checks:
        print(f"  {'WIN' if ok else 'LOSE'}  {name}")
        print(f"        {detail}")
    print()
    print("-------- by prompt (ok / rounds) --------")
    print(f"{'id':6} {'diff':4}  {'mom':>8} {'fast':>8} {'strong':>8}")
    for item in EVAL:
        pid = item["id"]

        def _ok_n(rows: list[dict[str, Any]]) -> str:
            rs = [r for r in rows if r["id"] == pid]
            return f"{sum(1 for r in rs if r['ok'])}/{len(rs)}"

        print(
            f"{pid:6} {item['diff']:4}  {_ok_n(mom.rows):>8} "
            f"{_ok_n(fast.rows):>8} {_ok_n(strong.rows):>8}"
        )
    print()
    print(f"OVERALL: {'WIN — MoM beat the baselines' if overall else 'LOSE — MoM did not beat the baselines'}")
    print("============================")

    report = {
        "overall": "WIN" if overall else "LOSE",
        "arms": {"mom": m, "always_fast": f, "always_strong": s},
        "checks": [{"name": n, "pass": ok, "detail": d} for n, ok, d in checks],
        "rows": {"mom": mom.rows, "always_fast": fast.rows, "always_strong": strong.rows},
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.json}")

    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
