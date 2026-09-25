"""Stub router — returns a route target (node name or model id)."""

from __future__ import annotations

import time
from typing import Any

from mom.directory import ModelDirectory
from mom.state import StateStore


class RouterModel:
    """
    Cheap stub router.

    Reads `state['route']` if set, else defaults to `stub.echo`.
    Sleeps briefly so speculation overlap is measurable.
    """

    def __init__(self, default_route: str = "stub.echo", delay_s: float = 0.05) -> None:
        self.default_route = default_route
        self.delay_s = delay_s

    def run(self, input: Any, state: StateStore) -> Any:
        time.sleep(self.delay_s)
        route = state.get("route") or self.default_route
        trace = state.get("trace") or []
        if not isinstance(trace, list):
            trace = list(trace)
        state.set("trace", [*trace, f"stub.router->{route}"])
        return {"route": route}


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.router",
        lambda: RouterModel(),
        tags={"stub", "router"},
        latency_class="cheap",
    )
