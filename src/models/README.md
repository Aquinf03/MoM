# Model catalog (stubs)

Path: `src/models/`.

## Production

Use the SDK runtime — **not** these stubs:

```python
from mom.runtime import build_directory, build_registry
```

See [`docs/production.md`](../../docs/production.md).

## Stubs (fixtures only)

Keep `MOM_INCLUDE_STUBS=0` unless running latency harnesses.

1. Create `src/models/my_model.py` with `run(self, input, state)`.
2. Export `register(directory)`.
3. Add to `_SEED` in `src/models/__init__.py`.

### Add a production adapter

Implement under `src/mom/adapters/` and register in `mom.runtime.build_directory`.
