"""MoM — Python surface for latency-transparent model composition."""

from __future__ import annotations

from mom.bus import Bus, Payload
from mom.directory import ModelDirectory
from mom.graph import Graph
from mom.scheduler import RunResult, Scheduler, plan_graph
from mom.state import StateStore

__version__ = "0.1.0"

try:
    from mom import _native as _native

    __version__ = _native.__version__
    core_version = _native.core_version
    ping = _native.ping
    NATIVE = True
except ImportError:  # pure-Python install / docs without extension
    NATIVE = False

    def core_version() -> str:
        return __version__

    def ping() -> str:
        return "mom-core (python fallback)"


__all__ = [
    "Bus",
    "Graph",
    "ModelDirectory",
    "NATIVE",
    "Payload",
    "RunResult",
    "Scheduler",
    "StateStore",
    "__version__",
    "core_version",
    "ping",
    "plan_graph",
]
