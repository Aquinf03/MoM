"""Reranker stub — ranks retrieval hits already in state."""

from __future__ import annotations

from typing import Any

from models._util import append_trace, as_text, sleep_ms
from mom.cancel import CancelToken
from mom.directory import ModelDirectory
from mom.state import StateStore


class RerankModel:
    """Reorders `state['retrieval']` / input hits; ~10ms."""

    def __init__(self, delay_ms: float = 10.0) -> None:
        self.delay_ms = delay_ms

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        hits = state.get("retrieval")
        if not isinstance(hits, list):
            if isinstance(input, dict) and isinstance(input.get("hits"), list):
                hits = list(input["hits"])
            else:
                hits = [{"id": "solo", "score": 1.0, "text": as_text(input)}]
        # Deterministic "rerank": reverse order + bump scores
        ranked = []
        for i, h in enumerate(reversed(hits)):
            if isinstance(h, dict):
                ranked.append({**h, "score": float(h.get("score", 0)) + 0.01 * (i + 1)})
            else:
                ranked.append({"id": str(i), "score": 1.0 - i * 0.1, "text": str(h)})
        append_trace(state, "stub.rerank")
        state.set("retrieval", ranked)
        return {"hits": ranked, "model": "stub.rerank", "modality": "retrieval"}


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.rerank",
        lambda: RerankModel(),
        tags={"stub", "rerank", "retrieval"},
        latency_class="cheap",
        modality="retrieval",
        size="base",
    )
