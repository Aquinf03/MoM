# Add a model

1. Create `models/my_model.py` with a class that implements `run(self, input, state)`.
2. Export `register(directory)` that calls `directory.register("my.id", factory, tags=...)`.
3. Add the module path to `_SEED` in `models/__init__.py` **or** call `register(...)` yourself.
4. Wire it into any `Graph` by id — `.add("node", "my.id")` — no changes to `mom-core` or the scheduler.

Same interface for classifiers, SLMs, LLMs, embedders, tools, transforms, …
