# Speculative routing — numbers vs single-model baseline

Proof lives in the harness (re-run anytime):

```bash
source .venv/bin/activate
python scripts/helpers/bench/latency_compare.py --rounds 30
```

## What is compared

| Series | Meaning |
| --- | --- |
| `baseline_slm` | Call `stub.slm` alone (no router, no graph) |
| `mom_hit` | `decision → speculate(slm)` when the router picks SLM |
| `mom_miss` | Same graph when the router picks LLM (forced hard) |

## Pass criteria (stubs)

1. **Orchestration overhead** on hit ≪ model variance (or `< 5ms` absolute when stub variance ≈ 0).
2. **Hit overhead vs baseline** `< 25ms` — router cost should be mostly overlapped.
3. **Miss penalty vs hit** `> 20ms` — wrong prior is *visible* and correct (LLM path).

When those three print `PASS` and `overall: PASS`, speculative routing is proven for the speculate-chat graph on this catalog. Real weights will change absolute numbers; the same harness is the gate.

## Related

- Tone/judgment: `scripts/helpers/bench/tone_smoke.py`
- Cancel on miss: `scripts/helpers/bench/cancel_smoke.py`
- Which shapes can hide latency: [`latency_hide.md`](./latency_hide.md)
