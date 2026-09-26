# Concepts

## Thesis

Compose independently trained models so the *external* experience matches one model: no latency tax, no tone flip, no exposed router.

## Pieces

| Piece | Role |
| --- | --- |
| **Model** | `run(input, state) → output` |
| **ModelDirectory** | id → factory + tags |
| **Graph** | nodes = ids; edges = depend \| speculate |
| **StateStore** | single-owner shared memory across hops/turns |
| **Bus** | hop payload (text/JSON default; embedding optional) |
| **Scheduler / run** | execute plan; overlap speculate; metrics |
| **Session** | multi-turn over one store |
| **GraphRegistry** | name → graph; pick from what’s in the directory |
| **LightPrior** | static default → frequency prior for likely winner |

## Speculate

Start the likely generator with the router. On **hit**, wall ≈ max(router, prior). On **miss**, cancel prior and run the routed model (correct, not hidden).

## Latency

Orchestration overhead must stay ≪ natural model variance. See [`latency_hide.md`](./latency_hide.md) for which shapes can hide work.

## Guarantees / non-guarantees

**Aims to provide (colocated v1, stub-proven):**

- One `run(...)` / `Session.say(...)` call surface
- Shared in-process state (no accidental network hop in the hot path)
- Speculative overlap + cooperative cancel
- Adapter stability: register by id, wire graphs as data

**Does not guarantee:**

- Hidden latency for serial route, pipelines, or heavy reconcile
- Cross-host shared state
- Bit-identical outputs across model versions
- Production SLAs on third-party model APIs (bring your own adapters)
