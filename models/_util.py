"""Shared helpers for seeded stub adapters (no real weights)."""

from __future__ import annotations

from typing import Any

from mom.cancel import CancelToken, sleep_ms as _cancelable_sleep
from mom.state import StateStore


def append_trace(state: StateStore, tag: str) -> None:
    trace = state.get("trace") or []
    if not isinstance(trace, list):
        trace = list(trace)
    state.set("trace", [*trace, tag])


def sleep_ms(ms: float, cancel: CancelToken | None = None) -> None:
    _cancelable_sleep(ms, cancel)


def as_text(input: Any) -> str:
    if isinstance(input, str):
        return input
    if isinstance(input, dict):
        for key in ("text", "prompt", "input", "query"):
            if key in input and isinstance(input[key], str):
                return input[key]
        return str(input)
    return str(input)
