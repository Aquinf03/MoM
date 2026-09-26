# Mixture of Models (MoM)

**Latency-transparent composition of arbitrary models — externally indistinguishable from one.**

MoM wires independently trained models (classifiers, SLMs, LLMs, decision/reasoning, embedders, vision, tools, …) behind a single interface. Users should not see seams: no latency tax, no tone/judgment flip-flops, no “which model am I talking to?”

Routing for cost or coverage is a solved problem. MoM’s target is different: **make composition invisible.**

## Why

Typical stacks optimize *which* model runs. MoM optimizes whether the user can tell that more than one ran.

That reframes the usual secondary issues:

| Concern | Usual framing | MoM framing |
| --- | --- | --- |
| Latency | Minimize cost | Hide or eliminate (speculate / shared memory) |
| State | Pass messages between models | One shared store; single owner |
| Composition | Fixed graph, swap nodes | Topology is data; adapts to what’s plugged in |

## vs adjacent ideas

| | Unit | Trained together? | Topology |
| --- | --- | --- | --- |
| **MoE** | Subnetworks in one model | Yes | Fixed, internal |
| **MoA** | Separate LLMs | No | Fixed layered refinement |
| **Routing / cascade** | Separate models | No | Fixed decision point |
| **MoM** | Any model kind | No | Dynamic; driven by the catalog |

MoE is training-time (one model that acts like many). MoM is systems-time (many models that act like one). MoA is the closest cousin, but locks one topology among LLMs; MoM treats graph shape as a first-class decision and treats **latency-invisibility** as the primary success metric.

## Shape of the system

```
models/          ← directory of any adapters (grow forever)
     ↓ register
ModelDirectory   ← id → adapter + tags
     ↓ wire
Graph            ← nodes = directory ids; edges = runtime data
     ↓ execute
mom-core (Rust)  ← shared state, speculative scheduler, timing
     ↓
mom (Python)     ← adapters, catalog, graph DSL
     ↓
one external run()  ← feels like a single model
```

- **Any model** implements one thin contract: `run(input, state) → output`.
- **Add a model** = drop into `models/`, register, reference by id in a graph. No runtime rewrite.
- **Graphs compose the catalog** — route, speculate, fan-out, reconcile, etc. are shapes you wire, not hardcoded product modes.

**Locked for v1:** colocated (in-process / same machine) · text/JSON bus default · prove a demo composition first, then dynamic graph selection · orchestration overhead ≪ natural model variance.

## Layout

```
crates/mom-core/   Rust hot path (state, scheduler, timing)
crates/mom-py/     PyO3 cdylib → mom._native
python/mom/        Python package (adapters, directory, graph DSL)
models/            Drop-in catalog — any model kind registers here
examples/          Runnable demos
bench/             Latency / seamlessness harnesses
```

```bash
# One-time: Rust (rustup) + project venv + SDK install
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
python3 -m venv .venv && source .venv/bin/activate
pip install maturin
cd python && maturin develop && cd ..
mom-ping
python examples/hello_mom.py
python bench/prod_matrix.py    # production-grade SDK matrix
```

Docs: [`docs/sdk.md`](./docs/sdk.md) · [`docs/adapter_guide.md`](./docs/adapter_guide.md) · [`docs/concepts.md`](./docs/concepts.md)

## Hard problems (honest)

**Interface** — Text buses are plug-and-play but pay serialization; embedding buses are fast but break true plug-and-play. Hard tradeoff, not a missing API.

**State** — Message-passing ownership becomes distributed systems. Shared store is cleaner and needs colocation.

**Latency** — Sequential hops show seams. Hide them with speculation (start the likely winner with the router) and keep routers near noise (low-ms). A heavy “decision LLM” on the critical path collapses the thesis.

**Topology** — Different plugs need different *graphs*, not just different nodes. `GraphRegistry` holds named shapes; `heuristic_select` picks among what’s satisfied by the directory. See [`docs/latency_hide.md`](./docs/latency_hide.md) for which compositions can hide latency.

## Success

Orchestration overhead smaller than the natural variance of the model calls themselves — functionally invisible, not literally zero.

**Pre-SDK gates** (re-run anytime):

```bash
python bench/done_means.py          # catalog width + drop-in + speculate proof + hello
python examples/hello_mom.py        # one command → colocated composition
python bench/latency_compare.py     # numbers vs single-SLM baseline
```

See [`docs/speculation_proof.md`](./docs/speculation_proof.md) and [`docs/latency_hide.md`](./docs/latency_hide.md).

## Open / deferred

| Topic | Status |
| --- | --- |
| Text vs embedding bus | Text default; embedding optional on a hop — tradeoff stands ([`docs/latency_hide.md`](./docs/latency_hide.md)) |
| Real model weights | Deferred — stubs prove contracts + latency gates; adapters swap in without runtime rewrite |
| Distributed / multi-host state | Deferred — v1 locked colocated |
| Public SDK package | Shipped from repo (`maturin develop` / `pip install -e python/`) — see [`docs/sdk.md`](./docs/sdk.md) |
| Second language client | Deferred until contracts stay green under prod matrix |

## Status

Python SDK installable from the repo; adapter/graph APIs marked stable (`mom.api`). Production matrix green (`bench/prod_matrix.py`). Optional second-language client still deferred.

## License

Copyright 2025 Aquin Labs Private Limited. Licensed under the [Apache License, Version 2.0](./LICENSE).
