"""Stub echo model — no weights; for wiring / latency harnesses."""

from __future__ import annotations

from typing import Any

from mom.directory import ModelDirectory
from mom.state import StateStore


class EchoModel:
    """Returns the input unchanged; tags mark it as a stub generator."""

    def run(self, input: Any, state: StateStore) -> Any:
        trace = state.get("trace") or []
        if not isinstance(trace, list):
            trace = list(trace)
        trace = [*trace, "stub.echo"]
        state.set("trace", trace)
        return input


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.echo",
        EchoModel,
        tags={"stub", "generator"},
        latency_class="instant",
    )
