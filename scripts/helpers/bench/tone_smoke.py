#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

"""
Tone / judgment smoke: same prompts through single SLM vs MoM.
On speculate *hit*, MoM's winner is stub.slm — text/model should match a
direct SLM call. On *miss*, MoM should use stub.llm and diverge.
  python bench/tone_smoke.py
"""
from __future__ import annotations
from typing import Any
from models import register_builtins
from mom import Graph, ModelDirectory, StateStore, run
PROMPTS = [
    "hi",
    "what is MoM?",
    "summarize latency transparency in one line",
]
def _text(out: Any) -> str:
    if isinstance(out, dict) and isinstance(out.get("text"), str):
        return out["text"]
    return str(out)
def _model(out: Any) -> str | None:
    if isinstance(out, dict) and isinstance(out.get("model"), str):
        return out["model"]
    return None
def slm_only(directory: ModelDirectory, prompt: str) -> Any:
    state = StateStore()
    return directory.create("stub.slm").run(prompt, state)
def mom_hit(directory: ModelDirectory, graph: Graph, prompt: str) -> Any:
    state = StateStore()
    return run(graph, prompt, directory, state=state)
def mom_miss(directory: ModelDirectory, graph: Graph, prompt: str) -> Any:
    state = StateStore()
    state.set("classification", "hard")
    return run(graph, prompt, directory, state=state)
def main() -> None:
    directory = ModelDirectory()
    register_builtins(directory)
    graph = (
        Graph()
        .add("router", "stub.decision")
        .add("fast", "stub.slm")
        .speculate("router", "fast")
    )
    print("=== tone smoke: single SLM vs MoM (hit) ===")
    hit_fail = 0
    for prompt in PROMPTS:
        base_out = slm_only(directory, prompt)
        mom = mom_hit(directory, graph, prompt)
        base_t, mom_t = _text(base_out), _text(mom.output)
        base_m, mom_m = _model(base_out), _model(mom.output)
        spec = (mom.metrics.get("spec") or {}).get("router")
        match = base_t == mom_t and base_m == mom_m == "stub.slm" and spec == "hit"
        if not match:
            hit_fail += 1
        print(f"  [{'PASS' if match else 'FAIL'}] prompt={prompt!r}")
        print(f"         SLM:  {base_t!r}  model={base_m}")
        print(f"         MoM:  {mom_t!r}  model={mom_m}  spec={spec}")
    print()
    print("=== judgment smoke: MoM miss may differ (LLM) ===")
    miss_ok = 0
    miss_prompts = PROMPTS[:2]
    for prompt in miss_prompts:
        base_out = slm_only(directory, prompt)
        mom = mom_miss(directory, graph, prompt)
        base_t, mom_t = _text(base_out), _text(mom.output)
        mom_m = _model(mom.output)
        spec = (mom.metrics.get("spec") or {}).get("router")
        differed = mom_m == "stub.llm" and spec == "miss" and mom_t != base_t
        if differed:
            miss_ok += 1
        print(f"  [{'PASS' if differed else 'FAIL'}] prompt={prompt!r}")
        print(f"         SLM:  {base_t!r}")
        print(f"         MoM:  {mom_t!r}  model={mom_m}  spec={spec}")
    print()
    hit_pass = hit_fail == 0
    miss_pass = miss_ok == len(miss_prompts)
    print(f"hit tone match: {'PASS' if hit_pass else 'FAIL'} ({len(PROMPTS) - hit_fail}/{len(PROMPTS)})")
    print(f"miss judgment diverge: {'PASS' if miss_pass else 'FAIL'} ({miss_ok}/{len(miss_prompts)})")
    overall = hit_pass and miss_pass
    print(f"overall: {'PASS' if overall else 'FAIL'}")
    raise SystemExit(0 if overall else 1)
if __name__ == "__main__":
    main()
