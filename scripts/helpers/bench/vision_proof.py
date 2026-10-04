#!/usr/bin/env python3
"""
Vision graphs on real pixels + real weights.

  caption_chat  = BLIP → MoM speculate chat
  caption_strong = BLIP → always-big chat
  torch_chat    = torchvision ResNet18 → MoM chat
  torch_strong  = torchvision → always-big chat

Images: weights/eval_images/*.png

  python scripts/helpers/bench/vision_proof.py --json results/vision_proof.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "scripts" / "helpers" / "bench")]

from eval_set import gold_ok  # noqa: E402
from mom import StateStore, run  # noqa: E402
from mom.runtime import build_directory, build_registry  # noqa: E402

IM = ROOT / "weights" / "eval_images"

EVAL: list[dict[str, Any]] = [
    {
        "id": "red",
        "diff": "easy",
        "image": IM / "solid_red.png",
        "prompt": "What color is this? One word.",
        "gold": "red",
    },
    {
        "id": "blue",
        "diff": "easy",
        "image": IM / "solid_blue.png",
        "prompt": "What color is this? One word.",
        "gold": "blue",
    },
    {
        "id": "green",
        "diff": "easy",
        "image": IM / "solid_green.png",
        "prompt": "What color is this? One word.",
        "gold": "green",
    },
    {
        "id": "circle",
        "diff": "easy",
        "image": IM / "circle_gray.png",
        "prompt": "Is there a circle? yes or no.",
        "gold": "yes",
    },
    {
        "id": "split",
        "diff": "hard",
        "image": IM / "split_red_blue.png",
        "prompt": (
            "Reason carefully. Name the two colors in this image. "
            "Reply with the two color words only."
        ),
        "gold_any": ["red", "blue"],
    },
]


def _text(out: Any) -> str:
    if isinstance(out, dict):
        for k in ("text", "caption", "top"):
            if isinstance(out.get(k), str):
                return out[k]
        return str(out)
    return str(out)


def _payload(item: dict[str, Any]) -> dict[str, str]:
    return {"image": str(item["image"]), "text": item["prompt"]}


def _run(directory, graph, item: dict[str, Any]) -> dict[str, Any]:
    state = StateStore()
    t0 = time.perf_counter()
    result = run(graph, _payload(item), directory, state=state)
    ms = (time.perf_counter() - t0) * 1000.0
    spec = result.metrics.get("spec") or {}
    outcome = next(iter(spec.values()), None) if isinstance(spec, dict) else None
    pred = _text(result.output)
    return {
        "ms": ms,
        "pred": pred,
        "ok": gold_ok(pred, item),
        "spec": outcome,
        "caption": state.get("caption"),
        "vision_top": state.get("vision_top"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    missing = [str(i["image"]) for i in EVAL if not Path(i["image"]).is_file()]
    if missing:
        print("missing images:", *missing, file=sys.stderr)
        return 2

    print("loading vision + chat models…", flush=True)
    directory = build_directory()
    reg = build_registry(directory)
    graphs = {
        "caption_chat": reg.get("caption_chat").graph,
        "caption_strong": reg.get("caption_strong").graph,
        "torch_chat": reg.get("torch_chat").graph,
        "torch_strong": reg.get("torch_strong").graph,
    }

    print("warmup…", flush=True)
    warm = _payload(EVAL[0])
    for g in graphs.values():
        run(g, warm, directory, state=StateStore())

    rows: list[dict[str, Any]] = []
    tallies: dict[str, dict[str, float]] = {
        n: {"n": 0, "ok": 0, "ms": 0.0} for n in graphs
    }

    for item in EVAL:
        print(f"\n=== {item['id']} {item['diff']}  {item['image'].name} ===", flush=True)
        for name, graph in graphs.items():
            out = _run(directory, graph, item)
            tallies[name]["n"] += 1
            tallies[name]["ok"] += int(out["ok"])
            tallies[name]["ms"] += out["ms"]
            rows.append({"id": item["id"], "arm": name, **{k: v for k, v in out.items() if k != "pred"}, "pred": out["pred"][:160]})
            print(
                f"  [{name:15}] {'OK' if out['ok'] else 'NO':2} {out['ms']:7.1f}ms "
                f"spec={out['spec']}  {out['pred'][:80]!r}",
                flush=True,
            )

    print("\n======== VISION SCOREBOARD ========")
    print(f"{'arm':16} {'acc':>8} {'mean_ms':>9}")
    for name, t in tallies.items():
        acc = t["ok"] / t["n"] if t["n"] else 0.0
        mean = t["ms"] / t["n"] if t["n"] else 0.0
        print(f"{name:16} {acc:8.0%} {mean:8.1f}ms")
    print("===================================")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"tallies": tallies, "rows": rows}, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
