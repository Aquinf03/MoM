"""Catalog of drop-in model adapters. Register into a ModelDirectory."""

from __future__ import annotations

from mom.directory import ModelDirectory


def register_builtins(directory: ModelDirectory) -> None:
    """Register all seeded catalog entries into `directory`."""
    from models.stub_echo import register as register_echo

    register_echo(directory)
