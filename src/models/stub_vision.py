"""Vision caption stub — image-ish input → text (same Model interface)."""

from __future__ import annotations

from typing import Any

from models._util import append_trace, as_text, sleep_ms
from mom.cancel import CancelToken
from mom.directory import ModelDirectory
from mom.state import StateStore


class VisionModel:
    """Fake VLM: treats input as an image ref / bytes proxy; ~40ms."""

    def __init__(self, delay_ms: float = 40.0, vendor: str = "local") -> None:
        self.delay_ms = delay_ms
        self.vendor = vendor

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        ref = as_text(input)
        if isinstance(input, dict) and "image" in input:
            ref = str(input["image"])
        caption = f"[vision:{self.vendor}] saw {ref[:48]}"
        append_trace(state, f"stub.vision.{self.vendor}")
        state.set("caption", caption)
        return {"text": caption, "model": f"stub.vision.{self.vendor}", "modality": "vision"}


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.vision.local",
        lambda: VisionModel(vendor="local", delay_ms=40.0),
        tags={"stub", "vision", "vlm", "local"},
        latency_class="medium",
        modality="vision",
        vendor="local",
        size="base",
    )
    directory.register(
        "stub.vision.cloud",
        lambda: VisionModel(vendor="cloud", delay_ms=90.0),
        tags={"stub", "vision", "vlm", "cloud"},
        latency_class="large",
        modality="vision",
        vendor="cloud",
        size="large",
    )
