"""Tiny text helpers shared by meta-layer (avoid importing models/)."""

from __future__ import annotations

from typing import Any


def as_text_light(input: Any) -> str:
    if isinstance(input, str):
        return input
    if isinstance(input, dict):
        for key in ("text", "prompt", "input", "query"):
            if key in input and isinstance(input[key], str):
                return input[key]
        return str(input)
    return str(input) if input is not None else ""
