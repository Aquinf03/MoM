"""Larger LLM stub — reads shared StateStore history."""

from __future__ import annotations

from typing import Any

from models._util import append_trace, as_text, sleep_ms
from mom.directory import ModelDirectory
from mom.cancel import CancelToken
from mom.state import StateStore
from mom.turn import history_text, turn_count


class LlmModel:
    """Heavy generator stub — ~80ms; continues the shared conversation."""

    def __init__(self, delay_ms: float = 80.0) -> None:
        self.delay_ms = delay_ms

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        text = as_text(input)
        ctx_turns = turn_count(state)
        _ = history_text(state, limit=12)
        append_trace(state, "stub.llm")
        reply = f"[llm t{ctx_turns}] {text}"
        return {
            "text": reply,
            "model": "stub.llm",
            "turn": ctx_turns,
            "tokens_est": max(8, len(text.split()) * 2),
        }


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.llm",
        lambda: LlmModel(),
        tags={"stub", "generator", "llm"},
        latency_class="large",
        modality="text",
    )
