#!/usr/bin/env python3
"""
Is MoM cheaper than always using the big model?

Not speed. Work = tokens generated × model size (135M vs 360M).
That's a stand-in for compute. No API bills here — local weights.

  python scripts/helpers/bench/mom_cost.py --rounds 2 --json results/mom_cost.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "scripts" / "helpers" / "bench")]

from eval_set import EVAL  # noqa: E402
from mom import StateStore, run  # noqa: E402
from mom.adapters.local_chat import reset_token_meter, token_meter_snapshot  # noqa: E402
from mom.runtime import ID_CHAT_FAST, ID_CHAT_STRONG, build_directory, build_registry  # noqa: E402

# Parameter counts for the two local chat models (millions).
FAST_M = 135
STRONG_M = 360


@dataclass
class Arm:
    name: str
    wall_ms: float = 0.0
    tok_fast: int = 0
    tok_strong: int = 0
    rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def tokens(self) -> int:
        return self.tok_fast + self.tok_strong

    @property
    def work(self) -> float:
        return self.tok_fast * FAST_M + self.tok_strong * STRONG_M


def _tokens_from_meter() -> tuple[int, int]:
    snap = token_meter_snapshot()
    return int(snap.get(ID_CHAT_FAST) or 0), int(snap.get(ID_CHAT_STRONG) or 0)


def _run(directory, graph, prompt: str) -> tuple[float, int, int]:
    reset_token_meter()
    state = StateStore()
    t0 = time.perf_counter()
    run(graph, prompt, directory, state=state)
    ms = (time.perf_counter() - t0) * 1000.0
    return ms, *_tokens_from_meter()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    print("loading models…", flush=True)
    directory = build_directory()
    reg = build_registry(directory)
    g_mom = reg.get("speculate_chat").graph
    g_fast = reg.get("direct_fast").graph
    g_strong = reg.get("direct_strong").graph

    print("warmup…", flush=True)
    for _ in range(max(1, args.warmup)):
        _run(directory, g_mom, "Say ok.")
        _run(directory, g_fast, "Say ok.")
        _run(directory, g_strong, "Say ok.")

    mom, fast, strong = Arm("mom"), Arm("always_fast"), Arm("always_strong")
    arms = (
        (mom, g_mom),
        (fast, g_fast),
        (strong, g_strong),
    )

    for r in range(args.rounds):
        for item in EVAL:
            for arm, graph in arms:
                ms, tf, ts = _run(directory, graph, item["prompt"])
                arm.wall_ms += ms
                arm.tok_fast += tf
                arm.tok_strong += ts
                arm.rows.append(
                    {
                        "id": item["id"],
                        "diff": item["diff"],
                        "ms": round(ms, 1),
                        "tok_fast": tf,
                        "tok_strong": ts,
                        "work": tf * FAST_M + ts * STRONG_M,
                    }
                )
                print(
                    f"[{arm.name:13}] r{r+1} {item['id']:4} {item['diff']:4} "
                    f"{ms:7.1f}ms  tok={tf+ts:3d} (fast {tf} / big {ts})  "
                    f"work={tf * FAST_M + ts * STRONG_M:.0f}",
                    flush=True,
                )

    cheaper = mom.work < strong.work
    vs_strong = (mom.work / strong.work) if strong.work else 0.0

    print()
    print("======== COST (work = tokens × model size) ========")
    print(f"{'arm':13} {'tokens':>8} {'fast_tok':>8} {'big_tok':>8} {'work':>12} {'wall_ms':>10}")
    for a in (mom, fast, strong):
        print(
            f"{a.name:13} {a.tokens:8d} {a.tok_fast:8d} {a.tok_strong:8d} "
            f"{a.work:12.0f} {a.wall_ms:9.0f}ms"
        )
    print()
    print(f"work units = (small tokens × {FAST_M}) + (big tokens × {STRONG_M})")
    print(f"MoM work vs always-big: {vs_strong:.2f}×  "
          f"({'CHEAPER' if cheaper else 'NOT cheaper'})")
    print(f"wall time  MoM {mom.wall_ms:.0f}ms vs big {strong.wall_ms:.0f}ms  "
          f"(speed is a separate question)")
    print("===================================================")

    report = {
        "overall": "CHEAPER" if cheaper else "NOT_CHEAPER",
        "fast_params_m": FAST_M,
        "strong_params_m": STRONG_M,
        "arms": {
            a.name: {
                "tokens": a.tokens,
                "tok_fast": a.tok_fast,
                "tok_strong": a.tok_strong,
                "work": a.work,
                "wall_ms": a.wall_ms,
            }
            for a in (mom, fast, strong)
        },
        "mom_work_vs_strong": vs_strong,
        "rows": {"mom": mom.rows, "always_fast": fast.rows, "always_strong": strong.rows},
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.json}")

    return 0 if cheaper else 1


if __name__ == "__main__":
    raise SystemExit(main())
