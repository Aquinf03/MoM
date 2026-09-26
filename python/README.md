# MoM Python SDK

Install from the **repo root** (see root README for full build instructions):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd python && maturin develop && cd ..
mom-ping
```

```python
from mom import Graph, ModelDirectory, Session, run
```

Docs: [`../docs/sdk.md`](../docs/sdk.md) · [`../docs/adapter_guide.md`](../docs/adapter_guide.md) · [`../docs/concepts.md`](../docs/concepts.md)
