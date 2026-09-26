# MoM Python SDK

Install from the repo (requires Rust toolchain + maturin):

```bash
cd python
python3 -m venv ../.venv && source ../.venv/bin/activate
pip install maturin
maturin develop
# or: pip install -e .
mom-ping
```

```python
from mom import Graph, ModelDirectory, Session, run
```

Docs: [`../docs/sdk.md`](../docs/sdk.md) · [`../docs/adapter_guide.md`](../docs/adapter_guide.md) · [`../docs/concepts.md`](../docs/concepts.md)
