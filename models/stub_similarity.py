"""Similarity / knn stub — consumes embedding vectors (embedding-bus hop)."""

from __future__ import annotations

import math
from typing import Any

from models._util import append_trace, sleep_ms
from models.stub_embedder import _pseudo_embedding
from mom.cancel import CancelToken
from mom.directory import ModelDirectory
from mom.state import StateStore


def _as_vec(input: Any, state: StateStore) -> list[float]:
    if isinstance(input, (list, tuple)) and input and isinstance(input[0], (int, float)):
        return [float(x) for x in input]
    if isinstance(input, dict) and "embedding" in input:
        return [float(x) for x in input["embedding"]]
    stored = state.get("embedding")
    if isinstance(stored, list) and stored:
        return [float(x) for x in stored]
    raise ValueError("similarity expects an embedding list (bus) or state['embedding']")


class SimilarityModel:
    """
    Score input vector against a tiny fixed gallery; ~3ms.

    Designed as the *consumer* of an embedding-bus hop from stub.embedder.
    """

    def __init__(self, delay_ms: float = 3.0, dims: int = 8) -> None:
        self.delay_ms = delay_ms
        self.gallery = {
            "alpha": _pseudo_embedding("alpha", dims),
            "beta": _pseudo_embedding("beta", dims),
            "gamma": _pseudo_embedding("gamma", dims),
        }

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        vec = _as_vec(input, state)
        scores = {name: _cosine(vec, g) for name, g in self.gallery.items()}
        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        append_trace(state, f"stub.similarity:{best}")
        state.set("similarity", {"best": best, "scores": scores})
        return {
            "best": best,
            "score": scores[best],
            "scores": scores,
            "model": "stub.similarity",
            "modality": "embedding",
        }


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(a[i] * a[i] for i in range(n))) or 1e-9
    nb = math.sqrt(sum(b[i] * b[i] for i in range(n))) or 1e-9
    return dot / (na * nb)


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.similarity",
        lambda: SimilarityModel(),
        tags={"stub", "similarity", "embedding"},
        latency_class="cheap",
        modality="embedding",
    )
