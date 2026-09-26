"""Retriever + tool stubs — non-generative modalities in the same directory."""

from __future__ import annotations

from typing import Any

from models._util import append_trace, as_text, sleep_ms
from mom.cancel import CancelToken
from mom.directory import ModelDirectory
from mom.state import StateStore


class RetrieverModel:
    """Fake dense/sparse retriever; ~12ms."""

    def __init__(self, delay_ms: float = 12.0, top_k: int = 3) -> None:
        self.delay_ms = delay_ms
        self.top_k = top_k

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        query = as_text(input)
        hits = [
            {"id": f"doc-{i}", "score": 1.0 - i * 0.1, "text": f"chunk about {query[:24]}"}
            for i in range(self.top_k)
        ]
        append_trace(state, "stub.retriever")
        state.set("retrieval", hits)
        return {"hits": hits, "model": "stub.retriever", "modality": "retrieval"}


class ToolModel:
    """Fake tool / function-call executor; ~8ms."""

    def __init__(self, delay_ms: float = 8.0) -> None:
        self.delay_ms = delay_ms

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        if isinstance(input, dict):
            name = str(input.get("tool") or input.get("name") or "echo")
            args = input.get("args") or input.get("arguments") or {}
        else:
            name = "echo"
            args = {"text": as_text(input)}
        result = {"ok": True, "tool": name, "args": args, "result": args}
        append_trace(state, f"stub.tool:{name}")
        state.set("tool_result", result)
        return {"text": str(result.get("result")), "model": "stub.tool", "tool": name}


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.retriever",
        lambda: RetrieverModel(),
        tags={"stub", "retriever", "rag"},
        latency_class="cheap",
        modality="retrieval",
        size="base",
    )
    directory.register(
        "stub.tool",
        lambda: ToolModel(),
        tags={"stub", "tool", "function"},
        latency_class="cheap",
        modality="tool",
        size="base",
    )
