"""Small language model (SLM) stub — reads shared turn history."""

from __future__ import annotations

from typing import Any

from models._util import append_trace, as_text, sleep_ms
from mom.directory import ModelDirectory
from mom.cancel import CancelToken
from mom.state import StateStore
from mom.turn import history_text, turn_count


class SlmModel:
    """Fast generator stub — short reply, ~30ms; reads StateStore history."""

    def __init__(self, delay_ms: float = 30.0) -> None:
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
        _ = history_text(state, limit=6)
        append_trace(state, "stub.slm")
        reply = f"[slm t{ctx_turns}] {text}"
        if ctx_turns:
            reply = f"{reply} 〈saw {ctx_turns} user turn(s)〉"
        # Assistant turn is committed by Session from the final output —
        # avoids duplicate history when speculation discards this prior.
        return {"text": reply, "model": "stub.slm", "turn": ctx_turns}


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.slm",
        lambda: SlmModel(),
        tags={"stub", "generator", "slm"},
        latency_class="small",
        modality="text",
    )
