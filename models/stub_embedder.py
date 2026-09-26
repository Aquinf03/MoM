"""Embedder stub — text → fixed-dim float vector (same Model interface)."""

from __future__ import annotations

import hashlib
from typing import Any

from models._util import append_trace, as_text, sleep_ms
from mom.directory import ModelDirectory
from mom.cancel import CancelToken
from mom.state import StateStore


def _pseudo_embedding(text: str, dims: int = 8) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    out: list[float] = []
    for i in range(dims):
        byte = digest[i % len(digest)]
        out.append((byte / 255.0) * 2.0 - 1.0)
    return out


class EmbedderModel:
    """Returns an embedding vector; ~5ms."""

    def __init__(self, dims: int = 8, delay_ms: float = 5.0) -> None:
        self.dims = dims
        self.delay_ms = delay_ms

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        text = as_text(input)
        vec = _pseudo_embedding(text, self.dims)
        append_trace(state, "stub.embedder")
        state.set("embedding", vec)
        return {"embedding": vec, "dims": self.dims, "model": "stub.embedder"}


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.embedder",
        lambda: EmbedderModel(),
        tags={"stub", "embedder"},
        latency_class="cheap",
        modality="embedding",
    )
