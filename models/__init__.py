"""Catalog of drop-in model adapters. Register into a ModelDirectory."""

from __future__ import annotations

from mom.directory import ModelDirectory

# Seed modules: same Model.run(input, state) interface, different roles.
# Grow span freely — graphs only ever reference directory ids.
_SEED = (
    "models.stub_echo",
    "models.stub_router",
    "models.stub_classifier",
    "models.stub_slm",
    "models.stub_llm",
    "models.stub_sizes",
    "models.stub_embedder",
    "models.stub_similarity",
    "models.stub_decision",
    "models.stub_reverse",
    "models.stub_vision",
    "models.stub_audio",
    "models.stub_tools",
)


def register_builtins(directory: ModelDirectory) -> None:
    """Register all seeded catalog entries into `directory`."""
    import importlib

    for mod_name in _SEED:
        mod = importlib.import_module(mod_name)
        mod.register(directory)


def catalog_ids() -> list[str]:
    """Ids that `register_builtins` installs (for docs / tests)."""
    d = ModelDirectory()
    register_builtins(d)
    return d.ids()
