"""Hop bus — text/JSON by default; pluggable transports."""

from __future__ import annotations

import json
import struct
from typing import Any


class _Payload:
    def __init__(self, kind: str, body: bytes) -> None:
        self._kind = kind
        self._body = body

    def kind(self) -> str:
        return self._kind

    def body(self) -> bytes:
        return self._body

    def as_text(self) -> str:
        return self._body.decode("utf-8")

    def __repr__(self) -> str:
        return f"Payload(kind={self._kind}, len={len(self._body)})"


class _PyBus:
    """Pure-Python fallback mirroring mom-core Bus."""

    def __init__(self, transport: str = "text_json") -> None:
        if transport in ("text_json", "text", "json"):
            self._kind = "text_json"
        elif transport in ("embedding", "embeddings"):
            self._kind = "embedding"
        else:
            raise ValueError(
                f"unknown transport {transport!r}; expected 'text_json' or 'embedding'"
            )

    @staticmethod
    def text_json() -> _PyBus:
        return _PyBus("text_json")

    @staticmethod
    def embedding() -> _PyBus:
        return _PyBus("embedding")

    def kind(self) -> str:
        return self._kind

    def encode(self, value: Any) -> _Payload:
        if self._kind == "text_json":
            return _Payload("text_json", json.dumps(value, separators=(",", ":")).encode())
        if not isinstance(value, (list, tuple)):
            raise ValueError("embedding transport expects a list of numbers")
        body = b"".join(struct.pack("<f", float(x)) for x in value)
        return _Payload("embedding", body)

    def decode(self, payload: _Payload) -> Any:
        if payload.kind() != self._kind:
            raise ValueError(
                f"payload kind mismatch: expected {self._kind}, got {payload.kind()}"
            )
        if self._kind == "text_json":
            return json.loads(payload.as_text())
        body = payload.body()
        if len(body) % 4 != 0:
            raise ValueError("embedding body length must be a multiple of 4")
        return list(struct.unpack(f"<{len(body) // 4}f", body))

    def roundtrip(self, value: Any) -> Any:
        return self.decode(self.encode(value))

    def __repr__(self) -> str:
        return f"Bus(kind={self._kind})"


try:
    from mom._native import Bus as Bus
    from mom._native import Payload as Payload
except ImportError:
    Bus = _PyBus  # type: ignore[misc, assignment]
    Payload = _Payload  # type: ignore[misc, assignment]

__all__ = ["Bus", "Payload"]
