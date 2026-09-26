"""MoM — Python surface for latency-transparent model composition.

Native when loaded: StateStore, Bus, ModelDirectory mirror, plan_graph, run_graph,
Trace metrics. Graph DSL + Scheduler stay in Python and call into the extension.
"""

from __future__ import annotations

from mom.bus import Bus, Payload
from mom.cancel import CancelToken, CancelledError
from mom.directory import ModelDirectory
from mom.graph import Graph
from mom.limits import ConcurrencyLimits, LimitExceeded, Limiter
from mom.prior import LightPrior, apply_prior_to_graph
from mom.scheduler import RunResult, Scheduler, plan_graph, run
from mom.session import Session
from mom.state import StateStore
from mom.turn import add_assistant, add_user, get_messages, turn_count

__version__ = "0.1.0"

try:
    from mom import _native as _native

    __version__ = _native.__version__
    core_version = _native.core_version
    ping = _native.ping
    NATIVE = True
except ImportError:
    NATIVE = False

    def core_version() -> str:
        return __version__

    def ping() -> str:
        return "mom-core (python fallback)"


__all__ = [
    "Bus",
    "CancelToken",
    "CancelledError",
    "ConcurrencyLimits",
    "Graph",
    "LightPrior",
    "LimitExceeded",
    "Limiter",
    "ModelDirectory",
    "NATIVE",
    "Payload",
    "RunResult",
    "Scheduler",
    "Session",
    "StateStore",
    "__version__",
    "add_assistant",
    "add_user",
    "apply_prior_to_graph",
    "core_version",
    "get_messages",
    "ping",
    "plan_graph",
    "run",
    "turn_count",
]
