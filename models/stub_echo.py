"""Generic echo / alt generator stubs for wiring tests."""

from __future__ import annotations

from typing import Any

from models._util import append_trace, sleep_ms
from mom.directory import ModelDirectory
from mom.cancel import CancelToken
from mom.state import StateStore


class EchoModel:
    """Returns the input unchanged; optional delay for speculation demos."""

    def __init__(self, delay_ms: float = 50.0, tag: str = "stub.echo") -> None:
        self.delay_ms = delay_ms
        self.tag = tag

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        append_trace(state, self.tag)
        return input


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.echo",
        lambda: EchoModel(delay_ms=50.0, tag="stub.echo"),
        tags={"stub", "generator"},
        latency_class="instant",
        modality="text",
    )
    directory.register(
        "stub.echo_alt",
        lambda: EchoModel(delay_ms=50.0, tag="stub.echo_alt"),
        tags={"stub", "generator"},
        latency_class="instant",
        modality="text",
    )
