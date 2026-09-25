"""Shared helpers for seeded stub adapters (no real weights)."""

from __future__ import annotations

import time
from typing import Any

from mom.state import StateStore


def append_trace(state: StateStore, tag: str) -> None:
    trace = state.get("trace") or []
    if not isinstance(trace, list):
        trace = list(trace)
    state.set("trace", [*trace, tag])


def sleep_ms(ms: float) -> None:
    if ms > 0:
        time.sleep(ms / 1000.0)


def as_text(input: Any) -> str:
    if isinstance(input, str):
        return input
    if isinstance(input, dict):
        for key in ("text", "prompt", "input", "query"):
            if key in input and isinstance(input[key], str):
                return input[key]
        return str(input)
    return str(input)
