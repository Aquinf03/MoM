"""Thin adapter contract — any model kind implements this."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Model(Protocol):
    """One contract for classifiers, SLMs, LLMs, embedders, tools, …"""

    def run(self, input: Any, state: dict[str, Any]) -> Any:
        """Execute against shared state; return output for this hop."""
        ...
