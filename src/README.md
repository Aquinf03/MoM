# MoM sources (`src/`)

- `mom/` — installable Python SDK
- `models/` — stub catalog for benches (not production)
- `crates/` — Rust hot path (`mom-core`, `mom-py` → `mom._native`)

```bash
# from repo root
maturin develop
mom version
```

Docs: [`../docs/sdk.md`](../docs/sdk.md) · [`../docs/production.md`](../docs/production.md)
