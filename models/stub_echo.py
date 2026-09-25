"""Stub echo model — no weights; for wiring / latency harnesses."""

from __future__ import annotations

from typing import Any

from mom.directory import ModelDirectory


class EchoModel:
    """Returns the input unchanged; tags mark it as a stub generator."""

    def run(self, input: Any, state: dict[str, Any]) -> Any:
        state.setdefault("trace", []).append("stub.echo")
        return input


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.echo",
        EchoModel,
        tags={"stub", "generator"},
        latency_class="instant",
    )
