"""Unrelated stub: reverse / playful transform — not a router or chat LM."""

from __future__ import annotations

from typing import Any

from models._util import append_trace, as_text, sleep_ms
from mom.directory import ModelDirectory
from mom.state import StateStore


class ReverseModel:
    """
    Toy transform model with no relation to chat routing.

    Proves a new adapter can drop into `models/` and join any graph
    without changes to mom-core / scheduler.
    """

    def __init__(self, delay_ms: float = 10.0) -> None:
        self.delay_ms = delay_ms

    def run(self, input: Any, state: StateStore) -> Any:
        sleep_ms(self.delay_ms)
        if isinstance(input, dict) and isinstance(input.get("text"), str):
            text = input["text"]
        else:
            text = as_text(input)
        append_trace(state, "stub.reverse")
        flipped = text[::-1]
        state.set("reversed", flipped)
        return {
            "text": flipped,
            "model": "stub.reverse",
            "chars": len(text),
        }


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.reverse",
        lambda: ReverseModel(),
        tags={"stub", "transform", "unrelated"},
        latency_class="cheap",
        modality="text",
    )
