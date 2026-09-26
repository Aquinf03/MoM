# Latency-hideable vs not

MoM’s thesis is composition that *feels* like one model. That only holds for
shapes where extra work fits under overlapped wall time (or is noise). Other
shapes are valid — they just show seams.

These notes go with the builtin registry shapes in `mom.shapes`.

## Can be latency-hidden (or already single-hop)

| Shape | Graph | Why |
| --- | --- | --- |
| **speculate** | `speculate_chat` | Router ∥ likely winner. On hit, wall ≈ max(router, prior); orchestration should stay ≪ model variance. |
| **single** | `vision_caption` | One model — nothing to hide. |

Miss path on speculate is *correct* but not hidden: you pay prior waste (mitigated by cancel) + the true model.

## Partially hideable

| Shape | Graph | What hides / what doesn’t |
| --- | --- | --- |
| **fan-out → reconcile** | `fanout_reconcile` | Sibling generators overlap → critical path ≈ max(gens). **Reconcile is serial** after the join (`latency_hideable=False` on `stub.reconcile`). User-visible merge cost remains. |

## Not latency-hidden (by design)

| Shape | Graph | Why |
| --- | --- | --- |
| **route (serial)** | `route_serial` | Router then generator, no overlap. Same decisions as speculate, full sum of latencies. |
| **pipeline** | `pipeline_transform` | Depend edges only. Each hop adds wall time. |
| **embed → score** | `embed_score` | Sequential vector hop. Embedding *bus* can cheapen packing; it does not overlap model work. |

## Rules of thumb

1. **Speculate** when a cheap router + likely default generator dominate traffic.
2. **Fan-out** when you truly need multiple views; budget reconcile as visible.
3. **Never** put a heavy decision LLM on the critical path and call it hidden.
4. Registry `GraphSpec.latency_hideable` is the machine-readable flag; this doc is the rationale.
5. Heuristic selection (`mom.select.heuristic_select`) prefers hideable chat graphs when the prompt looks like chat — it does not invent new physics.

## Measuring

Use `bench/latency_compare.py` for speculate hit/miss vs single-SLM, and
`bench/topology_smoke.py` for registry / fan-out wave timing. Pass criterion
remains: orchestration overhead ≪ natural model variance on the demo path.
