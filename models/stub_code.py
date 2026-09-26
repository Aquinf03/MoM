"""Code-ish stub — another modality behind the same Model.run contract."""

from __future__ import annotations

from typing import Any

from models._util import append_trace, as_text, sleep_ms
from mom.cancel import CancelToken
from mom.directory import ModelDirectory
from mom.state import StateStore


class CodeModel:
    """Pretend code completer; ~45ms."""

    def __init__(self, delay_ms: float = 45.0, vendor: str = "local") -> None:
        self.delay_ms = delay_ms
        self.vendor = vendor

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        prompt = as_text(input)
        body = f"# [{self.vendor}] completion\ndef answer():\n    return {prompt!r}\n"
        append_trace(state, f"stub.code.{self.vendor}")
        return {
            "text": body,
            "model": f"stub.code.{self.vendor}",
            "modality": "code",
        }


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.code.local",
        lambda: CodeModel(vendor="local"),
        tags={"stub", "code", "generator", "local"},
        latency_class="medium",
        modality="code",
        vendor="local",
        size="base",
    )
