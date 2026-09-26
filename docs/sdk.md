# MoM SDK

Installable Python package for latency-transparent composition of arbitrary models.

## Install (from repo)

```bash
# Rust once: https://rustup.rs  (`rustc --version`)
cd /path/to/mom
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # maturin
pip install -r requirements-dev.txt      # optional: pytest
cd python && maturin develop && cd ..
mom-ping
```

Full steps (rebuild, uninstall, tests): see the root [`README.md`](../README.md#build--install).

Editable install also works after maturin has built the extension:

```bash
cd python && pip install -e ".[dev]"
```

## Quick start

```python
from mom import Graph, ModelDirectory, StateStore, run

directory = ModelDirectory()

class Echo:
    def run(self, input, state, cancel=None):
        return {"text": str(input), "model": "echo"}

directory.register("echo", Echo, tags={"generator"})

graph = Graph().add("g", "echo")
result = run(graph, "hello", directory, state=StateStore())
print(result.output, result.metrics["total_ms"])
```

Seed stubs used in demos live in the repo `models/` tree (not required by the SDK core). Add them to `PYTHONPATH` or register your own adapters.

## Stable surface

Prefer:

```python
import mom
from mom import Graph, ModelDirectory, Session, run, Scheduler
from mom.adapter import Model
# or
from mom.api import STABLE_API
```

See [`adapter_guide.md`](./adapter_guide.md), [`concepts.md`](./concepts.md), [`latency_hide.md`](./latency_hide.md).

## Version

Package version tracks `mom.__version__` (aligned with `mom-core` when native is loaded).
