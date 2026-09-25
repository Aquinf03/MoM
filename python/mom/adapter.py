"""Thin adapter contract — any model kind implements this."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from mom.state import StateStore


@runtime_checkable
class Model(Protocol):
    """One contract for classifiers, SLMs, LLMs, embedders, tools, …"""

    def run(self, input: Any, state: StateStore) -> Any:
        """Execute against the shared StateStore; return output for this hop."""
        ...
