"""Cheap classifier stub — low-ms routing signal (not a full LLM)."""

from __future__ import annotations

from typing import Any

from models._util import append_trace, as_text, sleep_ms
from mom.directory import ModelDirectory
from mom.cancel import CancelToken
from mom.state import StateStore


class ClassifierModel:
    """
    Tiny stub classifier.

    Labels input as `easy` | `hard` from length / keywords.
    Delay ~2ms so it stays noise relative to generators.
    """

    def __init__(self, delay_ms: float = 2.0) -> None:
        self.delay_ms = delay_ms

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        text = as_text(input).lower()
        label = "hard" if (len(text) > 80 or "reason" in text or "complex" in text) else "easy"
        append_trace(state, f"stub.classifier:{label}")
        state.set("classification", label)
        return {"label": label, "text": as_text(input)}


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.classifier",
        lambda: ClassifierModel(),
        tags={"stub", "classifier", "router"},
        latency_class="cheap",
        modality="text",
    )
