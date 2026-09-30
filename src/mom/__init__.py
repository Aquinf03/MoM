"""MoM — Python SDK for latency-transparent model composition.

Stable imports::

    import mom
    from mom import Graph, ModelDirectory, Session, run
    from mom.config import Settings
    from mom.runtime import build_directory, build_registry
"""

from __future__ import annotations

from mom.adapter import Model
from mom.app import ChatReply, MoM
from mom.bus import Bus, Payload
from mom.cancel import CancelToken, CancelledError
from mom.config import Settings
from mom.directory import ModelDirectory
from mom.errors import AdapterAuthError, AdapterError, AdapterTimeout, ConfigError, MomError
from mom.graph import Edge, Graph, Node
from mom.health import health_check, readiness_check
from mom.limits import ConcurrencyLimits, LimitExceeded, Limiter
from mom.prior import LightPrior, apply_prior_to_graph
from mom.registry import GraphRegistry, GraphSpec
from mom.runtime import build_directory, build_registry, concurrency_limits
from mom.scheduler import RunResult, Scheduler, plan_graph, run, run_named
from mom.select import heuristic_select, select_graph
from mom.session import Session
from mom.shapes import register_builtin_shapes
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
    "AdapterAuthError",
    "AdapterError",
    "AdapterTimeout",
    "Bus",
    "CancelToken",
    "CancelledError",
    "ChatReply",
    "ConcurrencyLimits",
    "ConfigError",
    "Edge",
    "Graph",
    "GraphRegistry",
    "GraphSpec",
    "LightPrior",
    "LimitExceeded",
    "Limiter",
    "MoM",
    "Model",
    "ModelDirectory",
    "MomError",
    "NATIVE",
    "Node",
    "Payload",
    "RunResult",
    "Scheduler",
    "Session",
    "Settings",
    "StateStore",
    "__version__",
    "add_assistant",
    "add_user",
    "apply_prior_to_graph",
    "build_directory",
    "build_registry",
    "concurrency_limits",
    "core_version",
    "get_messages",
    "health_check",
    "heuristic_select",
    "ping",
    "plan_graph",
    "readiness_check",
    "register_builtin_shapes",
    "run",
    "run_named",
    "select_graph",
    "turn_count",
]
