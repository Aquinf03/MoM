"""Cancellation for speculative losers — cooperative, checkable mid-run."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING


class CancelledError(Exception):
    """Raised when a model observes a cancelled CancelToken."""


class CancelToken:
    """
    Cooperative cancel flag for in-flight model work.

    Speculative priors receive a token; on miss the scheduler calls `cancel()`
    so the loser can stop instead of burning GPU/CPU to completion.
    """

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        """Raise CancelledError if cancelled."""
        if self._event.is_set():
            raise CancelledError("speculative work cancelled")

    def wait(self, timeout_s: float) -> bool:
        """
        Wait up to `timeout_s` seconds.

        Returns True if cancelled during the wait, False on timeout.
        """
        return self._event.wait(timeout_s)


def sleep_ms(ms: float, cancel: CancelToken | None = None) -> None:
    """Sleep in small chunks so cancel can interrupt stub / blocking work."""
    if ms <= 0:
        return
    if cancel is None:
        import time

        time.sleep(ms / 1000.0)
        return
    remaining = ms / 1000.0
    # ~5ms slices: responsive without spinning
    slice_s = 0.005
    while remaining > 0:
        cancel.check()
        step = min(slice_s, remaining)
        if cancel.wait(step):
            raise CancelledError("speculative work cancelled during sleep")
        remaining -= step


if TYPE_CHECKING:
    pass
