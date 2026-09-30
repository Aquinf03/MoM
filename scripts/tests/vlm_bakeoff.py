"""VLM monolith vs MoM specialists (ViT + router + SLM/LLM) — bakeoff fixtures."""

from __future__ import annotations

from typing import Any

from mom.cancel import CancelToken, sleep_ms
from mom.directory import ModelDirectory
from mom.graph import Graph
from mom.state import StateStore
from mom.util_text import as_text_light


def _image_ref(input: Any) -> str:
    if isinstance(input, dict):
        if "image" in input:
            return str(input["image"])
        if "text" in input:
            return as_text_light(input)
    return as_text_light(input)


def _question(input: Any) -> str:
    if isinstance(input, dict):
        for k in ("question", "text", "prompt", "query"):
            if k in input and isinstance(input[k], str):
                return input[k]
    return as_text_light(input)


class MonolithVLM:
    """
    Arm A — one big vision-language model (expensive, does everything).

    Stub delays simulate a heavy VLM (~120ms).
    """

    def __init__(self, delay_ms: float = 120.0) -> None:
        self.delay_ms = delay_ms

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        img = _image_ref(input)
        q = _question(input)
        hard = _is_hard(q, state)
        text = f"[vlm] {img}: {q}" + (" (deep)" if hard else "")
        state.set("vision_path", "monolith")
        state.set("caption", f"vlm-caption:{img}")
        return {
            "text": text,
            "model": "bakeoff.vlm",
            "modality": "vision+language",
            "arm": "monolith",
            "hard": hard,
        }


class ViTEncoder:
    """Cheap vision tower — image → embedding + short caption (~15ms)."""

    def __init__(self, delay_ms: float = 15.0) -> None:
        self.delay_ms = delay_ms

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        img = _image_ref(input)
        # Deterministic pseudo-embedding from path/bytes proxy
        vec = [((ord(c) % 13) / 13.0) for c in img[:16]] or [0.1, 0.2, 0.3]
        caption = f"vit:{img[:40]}"
        state.set("embedding", vec)
        state.set("caption", caption)
        state.set("image_ref", img)
        state.set("vision_path", "specialists")
        # Pass question through for downstream language models
        q = _question(input)
        return {
            "text": q,
            "caption": caption,
            "embedding": vec,
            "image": img,
            "model": "bakeoff.vit",
            "modality": "vision",
        }


class VisionRouter:
    """Routes easy visual QA → SLM, hard → LLM (uses caption/question)."""

    def __init__(self, delay_ms: float = 8.0) -> None:
        self.delay_ms = delay_ms

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        forced = state.get("route")
        if isinstance(forced, str) and forced:
            return {"route": forced, "reason": "state"}
        q = _question(input)
        if state.get("classification") == "hard" or _is_hard(q, state):
            return {"route": "bakeoff.llm", "reason": "hard"}
        return {"route": "bakeoff.slm", "reason": "easy"}


class SpecialistSLM:
    """Fast language head on ViT caption + question (~25ms)."""

    def __init__(self, delay_ms: float = 25.0) -> None:
        self.delay_ms = delay_ms

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        caption = state.get("caption") or ""
        q = _question(input)
        text = f"[slm+vit] {caption} :: {q}"
        return {
            "text": text,
            "model": "bakeoff.slm",
            "modality": "text",
            "arm": "mom",
            "caption": caption,
        }


class SpecialistLLM:
    """Heavier language head for hard visual reasoning (~70ms)."""

    def __init__(self, delay_ms: float = 70.0) -> None:
        self.delay_ms = delay_ms

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        caption = state.get("caption") or ""
        emb = state.get("embedding") or []
        q = _question(input)
        text = f"[llm+vit] {caption} emb_dim={len(emb)} :: {q} (reasoned)"
        return {
            "text": text,
            "model": "bakeoff.llm",
            "modality": "text",
            "arm": "mom",
            "caption": caption,
        }


def _is_hard(q: str, state: StateStore) -> bool:
    if state.get("classification") == "hard":
        return True
    ql = q.lower()
    return any(k in ql for k in ("why", "reason", "compare", "diagram", "how many"))


def register_bakeoff(directory: ModelDirectory) -> None:
    directory.register(
        "bakeoff.vlm",
        MonolithVLM,
        tags={"vlm", "monolith", "bakeoff"},
        modality="vision",
        latency_class="xlarge",
    )
    directory.register(
        "bakeoff.vit",
        ViTEncoder,
        tags={"vit", "vision", "bakeoff"},
        modality="vision",
        latency_class="cheap",
    )
    directory.register(
        "bakeoff.router",
        VisionRouter,
        tags={"router", "bakeoff"},
        modality="text",
        latency_class="cheap",
    )
    directory.register(
        "bakeoff.slm",
        SpecialistSLM,
        tags={"generator", "slm", "bakeoff"},
        modality="text",
        latency_class="small",
    )
    directory.register(
        "bakeoff.llm",
        SpecialistLLM,
        tags={"generator", "llm", "bakeoff"},
        modality="text",
        latency_class="large",
    )


def graph_monolith() -> Graph:
    """Arm A: single VLM."""
    return Graph().add("vlm", "bakeoff.vlm")


def graph_mom_specialists() -> Graph:
    """Arm B: ViT → router ∥ speculate(SLM); miss → LLM."""
    return (
        Graph()
        .add("vit", "bakeoff.vit")
        .add("router", "bakeoff.router")
        .add("gen", "bakeoff.slm")
        .link("vit", "router")
        .speculate("router", "gen")
    )
