# Mixture of Models (MoM)

**What this is:** a production composition runtime. You plug in *any* models (LLMs, tools, retrievers, classifiers, …), wire them as graphs, and expose **one** call surface that behaves like a single model — shared state, speculative routing, limits, HTTP API.

**What this is not:** a chatbot toy, a prompt playground, or a stub zoo. Stubs exist only for latency benches.

## Build products on it

```python
from mom import MoM, Graph

app = MoM()  # env → local HF / path weights (MOM_BACKEND=local)

@app.model("billing.lookup", tags={"tool"})
class BillingLookup:
    def run(self, input, state, cancel=None):
        return {"text": "invoice #9 is unpaid ($42)", "model": "billing.lookup"}

app.add_graph(
    "support",
    Graph()
    .add("billing", "billing.lookup")
    .add("router", "prod.router")
    .add("gen", "prod.chat.fast")
    .link("billing", "router")
    .speculate("router", "gen"),
    requires={"billing.lookup", "prod.router", "prod.chat.fast", "prod.chat.strong"},
    latency_hideable=True,
)

print(app.chat("why was I charged?", graph="support").text)
```

Starter product:

```bash
pip install -r requirements-local.txt
cp -n .env.example .env
# set MOM_CHAT_FAST to a Hub id or ./path/to/weights
PYTHONPATH=src:scripts/helpers python -m apps.assistant once "What's my ticket status?"
```

## Build & install

```bash
# Prerequisites: Python ≥3.10, Rust via https://rustup.rs
git clone https://github.com/aquinlabs/mom.git && cd mom
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt -r requirements-local.txt
maturin develop
mom-ping
cp .env.example .env
```

## Layout

```
src/mom/                      SDK (MoM(), adapters, runtime, server)
src/models/                   Stub fixtures for benches ONLY
src/crates/                   Rust hot path (mom-core, mom-py → mom._native)
scripts/helpers/bench/        Latency / smoke harnesses
scripts/helpers/examples/     Small demos
scripts/helpers/apps/         Full products built on MoM
scripts/tests/                Pytest matrix
docs/                         Production / adapter / latency docs
```

## Verify

```bash
pytest -q
python scripts/helpers/bench/prod_matrix.py
python scripts/helpers/examples/hello_mom.py
python scripts/helpers/bench/done_means.py
```

## Docs

| Doc | |
| --- | --- |
| [`docs/production.md`](./docs/production.md) | Deploy, env, HTTP, Docker |
| [`docs/adapter_guide.md`](./docs/adapter_guide.md) | Add a model |
| [`docs/latency_hide.md`](./docs/latency_hide.md) | What can hide latency |
| [`docs/concepts.md`](./docs/concepts.md) | Guarantees / non-guarantees |

## Out of scope (for now)

- PyPI publish — install from this repo
- Multi-host shared state — v1 is colocated

## License

Copyright 2025 Aquin Labs Private Limited. Licensed under the [Apache License, Version 2.0](./LICENSE).
