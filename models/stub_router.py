"""Stub router — returns a route target (node name or model id)."""

from __future__ import annotations

from typing import Any

from models._util import append_trace, sleep_ms
from mom.directory import ModelDirectory
from mom.cancel import CancelToken
from mom.state import StateStore


class RouterModel:
    """
    Cheap stub router.

    Reads `state['route']` if set, else defaults to `stub.echo`.
    """

    def __init__(self, default_route: str = "stub.echo", delay_ms: float = 50.0) -> None:
        self.default_route = default_route
        self.delay_ms = delay_ms

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        sleep_ms(self.delay_ms, cancel)
        route = state.get("route") or self.default_route
        append_trace(state, f"stub.router->{route}")
        return {"route": route}


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.router",
        lambda: RouterModel(),
        tags={"stub", "router"},
        latency_class="cheap",
        modality="text",
    )
