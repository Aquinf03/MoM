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
crates/mom-core/     Rust hot path (state, scheduler, timing)
crates/mom-py/       PyO3 cdylib → mom._native
python/mom/          Python SDK (adapters, directory, graph DSL)
models/              Drop-in catalog — any model kind registers here
examples/            Runnable demos
bench/               Latency / seamlessness harnesses
tests/               Production-grade SDK matrix (pytest)
docs/                SDK / adapter / latency docs
requirements.txt     Build/install Python deps
requirements-dev.txt Test extras (pytest)
```

## Prerequisites

| Tool | Version | Notes |
| --- | --- | --- |
| Python | ≥ 3.10 | 3.10–3.14 tested |
| Rust | stable via [rustup](https://rustup.rs) | needed to compile `mom._native` |
| pip / venv | stdlib | |

macOS / Linux / Windows (MSVC + rustup) should work; examples below use a Unix shell.

## Build & install

From the **repo root**:

```bash
# 1) Rust (skip if `rustc --version` already works)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# restart the shell or: source "$HOME/.cargo/env"
rustc --version

# 2) Clone & venv
git clone https://github.com/aquinlabs/mom.git
cd mom
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3) Python build deps
pip install --upgrade pip
pip install -r requirements.txt           # maturin
# optional, for pytest matrix:
pip install -r requirements-dev.txt

# 4) Build the Rust extension and install the `mom` SDK (editable)
cd python
maturin develop
cd ..

# 5) Sanity check
mom-ping
python -c "import mom; print(mom.__version__, mom.NATIVE, mom.ping())"
```

`maturin develop` compiles `crates/mom-py` → `mom._native` and installs the `mom` package into the active venv (editable). Equivalent after a successful develop:

```bash
cd python && pip install -e ".[dev]" && cd ..
```

### Rebuild after Rust/Python changes

```bash
source .venv/bin/activate
cd python && maturin develop && cd ..
```

### Uninstall

```bash
pip uninstall mom
```

## Quick start

```bash
source .venv/bin/activate
python examples/hello_mom.py
```

```python
from mom import Graph, ModelDirectory, StateStore, run

directory = ModelDirectory()

class Echo:
    def run(self, input, state, cancel=None):
        return {"text": str(input), "model": "echo"}

directory.register("echo", lambda: Echo(), tags={"generator"})
result = run(Graph().add("g", "echo"), "hello", directory, state=StateStore())
print(result.output)
```

Seed stubs used by demos live under `models/` (add the repo root to `PYTHONPATH` or run examples from the repo as shown — they set paths themselves).

## Verify / test

```bash
source .venv/bin/activate

# One-command demo
python examples/hello_mom.py

# Production-grade SDK matrix (needs requirements-dev.txt)
python bench/prod_matrix.py
# or: pytest -q

# Pre-SDK / latency gates
python bench/done_means.py
python bench/latency_compare.py
```

## Docs

| Doc | Content |
| --- | --- |
| [`docs/sdk.md`](./docs/sdk.md) | Install + stable surface |
| [`docs/adapter_guide.md`](./docs/adapter_guide.md) | How to add a model |
| [`docs/concepts.md`](./docs/concepts.md) | Guarantees / non-guarantees |
| [`docs/latency_hide.md`](./docs/latency_hide.md) | Which graph shapes hide latency |
| [`docs/speculation_proof.md`](./docs/speculation_proof.md) | Speculate vs single-model baseline |

## Hard problems (honest)

**Interface** — Text buses are plug-and-play but pay serialization; embedding buses are fast but break true plug-and-play. Hard tradeoff, not a missing API.

**State** — Message-passing ownership becomes distributed systems. Shared store is cleaner and needs colocation.

**Latency** — Sequential hops show seams. Hide them with speculation (start the likely winner with the router) and keep routers near noise (low-ms). A heavy “decision LLM” on the critical path collapses the thesis.

**Topology** — Different plugs need different *graphs*, not just different nodes. `GraphRegistry` holds named shapes; `heuristic_select` picks among what’s satisfied by the directory.

## Success

Orchestration overhead smaller than the natural variance of the model calls themselves — functionally invisible, not literally zero.

## Open / deferred

| Topic | Status |
| --- | --- |
| Text vs embedding bus | Text default; embedding optional on a hop |
| Real model weights | Deferred — stubs prove contracts; adapters swap in without runtime rewrite |
| Distributed / multi-host state | Deferred — v1 locked colocated |
| Second language client | Deferred until contracts stay green under prod matrix |

## Status

Python SDK installable from the repo (`requirements.txt` + `maturin develop`). Adapter/graph APIs marked stable (`mom.api`). Production matrix: `bench/prod_matrix.py`.

## License

Copyright 2025 Aquin Labs Private Limited. Licensed under the [Apache License, Version 2.0](./LICENSE).
