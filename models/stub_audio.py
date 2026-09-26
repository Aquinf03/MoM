"""ASR / TTS stubs — audio modality stand-ins behind the same adapter."""

from __future__ import annotations

from typing import Any

from models._util import append_trace, as_text, sleep_ms
from mom.cancel import CancelToken
from mom.directory import ModelDirectory
from mom.state import StateStore


class AsrModel:
    """Speech→text stub; ~35ms."""

    def __init__(self, delay_ms: float = 35.0, vendor: str = "local") -> None:
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
        if isinstance(input, dict) and "audio" in input:
            ref = str(input["audio"])
        text = f"[asr:{self.vendor}] transcript({ref[:32]})"
        append_trace(state, f"stub.asr.{self.vendor}")
        state.set("transcript", text)
        return {"text": text, "model": f"stub.asr.{self.vendor}", "modality": "audio"}


class TtsModel:
    """Text→speech stub; returns a fake audio ref; ~50ms."""

    def __init__(self, delay_ms: float = 50.0, vendor: str = "local") -> None:
        self.delay_ms = delay_ms
        self.vendor = vendor

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        text = as_text(input)
        audio_ref = f"audio://{self.vendor}/{hash(text) & 0xFFFF:04x}"
        append_trace(state, f"stub.tts.{self.vendor}")
        state.set("audio_ref", audio_ref)
        return {
            "audio": audio_ref,
            "text": text,
            "model": f"stub.tts.{self.vendor}",
            "modality": "audio",
        }


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.asr.local",
        lambda: AsrModel(vendor="local"),
        tags={"stub", "asr", "audio", "local"},
        latency_class="medium",
        modality="audio",
        vendor="local",
        size="base",
    )
    directory.register(
        "stub.tts.local",
        lambda: TtsModel(vendor="local"),
        tags={"stub", "tts", "audio", "local"},
        latency_class="medium",
        modality="audio",
        vendor="local",
        size="base",
    )
