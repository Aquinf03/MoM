"""Thin adapter contract — any model kind implements this."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from mom.cancel import CancelToken
from mom.state import StateStore


@runtime_checkable
class Model(Protocol):
    """One contract for classifiers, SLMs, LLMs, embedders, tools, …"""

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        """
        Execute against the shared StateStore; return output for this hop.

        Optional `cancel`: cooperative token for speculative losers. Models that
        can stop mid-flight should call `cancel.check()` / honor cancel in waits.
        """
        ...
