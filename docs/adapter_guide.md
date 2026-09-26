# Adapter guide

One contract. Any model kind.

## Contract

```python
from typing import Any
from mom.adapter import Model  # Protocol
from mom import StateStore, CancelToken

class MyModel:  # structural — no base class required
    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        cancel and cancel.check()
        state.set("my.key", ...)
        return {"text": "...", "model": "my.id"}
```

`isinstance(instance, Model)` works (`runtime_checkable`).

## Register

```python
from mom import ModelDirectory

directory = ModelDirectory()
directory.register(
    "vendor.my_model",
    lambda: MyModel(),
    tags={"generator", "vendor"},
    modality="text",
    latency_class="small",
)
```

Graphs reference **ids**, never Python classes:

```python
from mom import Graph
Graph().add("gen", "vendor.my_model")
```

## Rules

1. **No runtime rewrite** — new capability = new adapter file + `register` + graph id.
2. **Shared state** — read/write `StateStore` by key; do not invent message-passing ownership.
3. **Cancel** — speculative losers may receive a token; honor it in sleeps/loops when cheap.
4. **Output** — any JSON-friendly value; `{text, model}` is the common chat shape Session understands.
5. **Tags / meta** — optional; used by heuristics and docs, not by the hot path.

## Repo catalog pattern

The `models/` directory in this repo is a drop-in catalog of stubs. Copy the pattern for real weights; the SDK does not hardcode those modules.
