"""Backpressure / concurrency limits for colocated MoM runs."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


class LimitExceeded(Exception):
    """Raised when a concurrency limit cannot be acquired in time."""


@dataclass(frozen=True)
class ConcurrencyLimits:
    """
    Caps in-flight work so one machine doesn't melt.

    - `max_runs`: concurrent `Scheduler.run` / `mom.run` calls
    - `max_model_workers`: concurrent model invocations (incl. speculative priors)
    - `acquire_timeout_s`: wait budget; `None` waits forever, `0` fails immediately
    """

    max_runs: int = 8
    max_model_workers: int = 16
    acquire_timeout_s: float | None = None

    def __post_init__(self) -> None:
        if self.max_runs < 1:
            raise ValueError("max_runs must be >= 1")
        if self.max_model_workers < 1:
            raise ValueError("max_model_workers must be >= 1")


class Limiter:
    """Process-local semaphores enforcing a ConcurrencyLimits policy."""

    def __init__(self, limits: ConcurrencyLimits | None = None) -> None:
        self.limits = limits or ConcurrencyLimits()
        self._run_sem = threading.BoundedSemaphore(self.limits.max_runs)
        self._model_sem = threading.BoundedSemaphore(self.limits.max_model_workers)
        self._lock = threading.Lock()
        self._runs_active = 0
        self._models_active = 0
        self._runs_rejected = 0
        self._models_rejected = 0
        self._runs_waited_ms = 0.0

    @property
    def runs_active(self) -> int:
        with self._lock:
            return self._runs_active

    @property
    def models_active(self) -> int:
        with self._lock:
            return self._models_active

    @property
    def runs_rejected(self) -> int:
        with self._lock:
            return self._runs_rejected

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            return {
                "max_runs": self.limits.max_runs,
                "max_model_workers": self.limits.max_model_workers,
                "runs_active": self._runs_active,
                "models_active": self._models_active,
                "runs_rejected": self._runs_rejected,
                "models_rejected": self._models_rejected,
                "runs_waited_ms": self._runs_waited_ms,
            }

    def _acquire(self, sem: threading.BoundedSemaphore, kind: str) -> float:
        timeout = self.limits.acquire_timeout_s
        t0 = time.perf_counter()
        if timeout is None:
            ok = sem.acquire(blocking=True)
        elif timeout <= 0:
            ok = sem.acquire(blocking=False)
        else:
            ok = sem.acquire(blocking=True, timeout=timeout)
        waited = (time.perf_counter() - t0) * 1000.0
        if not ok:
            with self._lock:
                if kind == "run":
                    self._runs_rejected += 1
                else:
                    self._models_rejected += 1
            raise LimitExceeded(
                f"{kind} concurrency limit exceeded "
                f"(timeout={timeout!r}, limits={self.limits})"
            )
        return waited

    @contextmanager
    def run_slot(self) -> Iterator[float]:
        """Acquire a slot for one top-level graph run. Yields wait time in ms."""
        waited = self._acquire(self._run_sem, "run")
        with self._lock:
            self._runs_active += 1
            self._runs_waited_ms += waited
        try:
            yield waited
        finally:
            with self._lock:
                self._runs_active -= 1
            self._run_sem.release()

    @contextmanager
    def model_slot(self) -> Iterator[None]:
        """Acquire a slot for one model invocation (router, prior, generator, …)."""
        self._acquire(self._model_sem, "model")
        with self._lock:
            self._models_active += 1
        try:
            yield
        finally:
            with self._lock:
                self._models_active -= 1
            self._model_sem.release()
