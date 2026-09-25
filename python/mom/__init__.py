"""MoM — Python surface for latency-transparent model composition."""

from __future__ import annotations

from mom.directory import ModelDirectory
from mom.graph import Graph

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
    "Graph",
    "ModelDirectory",
    "NATIVE",
    "__version__",
    "core_version",
    "ping",
]
