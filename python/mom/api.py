"""Stable SDK exports — prefer `import mom` or `from mom.api import ...`.

This module re-exports the frozen public surface for v0.1. Anything not listed
here is internal and may change without notice.
"""

from __future__ import annotations

from mom.adapter import Model
from mom.bus import Bus, Payload
from mom.cancel import CancelToken, CancelledError
from mom.directory import ModelDirectory
from mom.graph import Edge, Graph, Node
from mom.limits import ConcurrencyLimits, LimitExceeded, Limiter
from mom.prior import LightPrior, apply_prior_to_graph
from mom.registry import GraphRegistry, GraphSpec
from mom.scheduler import RunResult, Scheduler, plan_graph, run, run_named
from mom.select import heuristic_select, select_graph
from mom.session import Session
from mom.shapes import register_builtin_shapes
from mom.state import StateStore
from mom.turn import add_assistant, add_user, get_messages, turn_count

# Lazy version/native to avoid import cycles when mom.__init__ is loading.
def __getattr__(name: str):
    if name in {"__version__", "NATIVE", "core_version", "ping"}:
        import mom as _pkg

        return getattr(_pkg, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


STABLE_API = (
    "Bus",
    "CancelToken",
    "CancelledError",
    "ConcurrencyLimits",
    "Edge",
    "Graph",
    "GraphRegistry",
    "GraphSpec",
    "LightPrior",
    "LimitExceeded",
    "Limiter",
    "Model",
    "ModelDirectory",
    "NATIVE",
    "Node",
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
    "heuristic_select",
    "ping",
    "plan_graph",
    "register_builtin_shapes",
    "run",
    "run_named",
    "select_graph",
    "turn_count",
)

__all__ = list(STABLE_API)
