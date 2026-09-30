"""Shout transform stub — example of a drop-in catalog entry."""

from __future__ import annotations

from typing import Any

from models._util import append_trace, as_text, sleep_ms
from mom.cancel import CancelToken
from mom.directory import ModelDirectory
from mom.state import StateStore


class ShoutModel:
    """Uppercases text; ~4ms. Exists to prove add-model = file + register."""

    def __init__(self, delay_ms: float = 4.0) -> None:
        self.delay_ms = delay_ms

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        text = as_text(input).upper()
        append_trace(state, "stub.shout")
        return {"text": text, "model": "stub.shout", "modality": "text"}


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.shout",
        lambda: ShoutModel(),
        tags={"stub", "transform"},
        latency_class="cheap",
        modality="text",
    )
