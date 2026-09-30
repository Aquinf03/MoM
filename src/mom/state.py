"""Shared state surface — prefers native mom-core store, dict fallback otherwise."""

from __future__ import annotations

from typing import Any


class _DictStateStore:
    """Pure-Python fallback when the native extension is unavailable."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def remove(self, key: str) -> Any:
        return self._data.pop(key, None)

    def contains(self, key: str) -> bool:
        return key in self._data

    def keys(self) -> list[str]:
        return sorted(self._data)

    def clear(self) -> None:
        self._data.clear()

    def snapshot(self) -> dict[str, Any]:
        return dict(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in self._data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __repr__(self) -> str:
        return f"StateStore(len={len(self._data)})"


try:
    from mom._native import StateStore as StateStore
except ImportError:
    StateStore = _DictStateStore  # type: ignore[misc, assignment]

__all__ = ["StateStore"]
