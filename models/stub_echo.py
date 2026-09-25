"""Stub echo model — no weights; for wiring / latency harnesses."""

from __future__ import annotations

import time
from typing import Any

from mom.directory import ModelDirectory
from mom.state import StateStore


class EchoModel:
    """Returns the input unchanged; optional delay for speculation demos."""

    def __init__(self, delay_s: float = 0.05, tag: str = "stub.echo") -> None:
        self.delay_s = delay_s
        self.tag = tag

    def run(self, input: Any, state: StateStore) -> Any:
        time.sleep(self.delay_s)
        trace = state.get("trace") or []
        if not isinstance(trace, list):
            trace = list(trace)
        state.set("trace", [*trace, self.tag])
        return input


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.echo",
        lambda: EchoModel(delay_s=0.05, tag="stub.echo"),
        tags={"stub", "generator"},
        latency_class="instant",
    )
    directory.register(
        "stub.echo_alt",
        lambda: EchoModel(delay_s=0.05, tag="stub.echo_alt"),
        tags={"stub", "generator"},
        latency_class="instant",
    )
