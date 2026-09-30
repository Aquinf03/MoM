"""Multi-turn session — one StateStore reused across runs."""

from __future__ import annotations

from typing import Any

from mom.bus import Bus
from mom.directory import ModelDirectory
from mom.graph import Graph
from mom.limits import ConcurrencyLimits, Limiter
from mom.prior import LightPrior
from mom.registry import GraphRegistry
from mom.scheduler import RunResult, run, run_named
from mom.state import StateStore
from mom.turn import add_assistant, add_user, get_messages, turn_count


def _assistant_content(output: Any) -> tuple[str, str | None]:
    if isinstance(output, dict):
        text = output.get("text")
        if isinstance(text, str):
            model = output.get("model")
            return text, model if isinstance(model, str) else None
        return str(output), None
    return str(output), None


class Session:
    """
    Holds the authoritative StateStore for a conversation.

    Each `say()` appends the user turn, runs the graph on that same store, then
    commits the assistant turn from the final output. Models read history from
    the store — nothing is passed as serialized messages between hops.

    Pass either a fixed `graph`, or a `registry` (+ optional `graph_name`) to
    pick topology from what's in the directory.
    """

    def __init__(
        self,
        directory: ModelDirectory,
        graph: Graph | None = None,
        *,
        registry: GraphRegistry | None = None,
        graph_name: str | None = None,
        auto_select: bool = False,
        state: StateStore | None = None,
        bus: Bus | None = None,
        limits: ConcurrencyLimits | Limiter | None = None,
        prior: LightPrior | None = None,
    ) -> None:
        if graph is None and registry is None:
            raise ValueError("Session needs a graph or a registry")
        self.directory = directory
        self.graph = graph
        self.registry = registry
        self.graph_name = graph_name
        self.auto_select = auto_select
        self.state = state or StateStore()
        self.bus = bus
        self.limits = limits
        self.prior = prior

    @property
    def messages(self) -> list[dict[str, Any]]:
        return get_messages(self.state)

    @property
    def turns(self) -> int:
        return turn_count(self.state)

    def say(self, text: str) -> RunResult:
        """One user turn against the shared store + graph."""
        add_user(self.state, text)
        if self.registry is not None and (self.auto_select or self.graph is None):
            result = run_named(
                None if self.auto_select else self.graph_name,
                text,
                self.directory,
                self.registry,
                state=self.state,
                bus=self.bus,
                limits=self.limits,
                prior=self.prior,
            )
        else:
            assert self.graph is not None
            result = run(
                self.graph,
                text,
                self.directory,
                state=self.state,
                bus=self.bus,
                limits=self.limits,
                prior=self.prior,
            )
        # Native run may return a twin StateStore handle that holds the writes.
        if result.state is not None:
            self.state = result.state
        content, model = _assistant_content(result.output)
        add_assistant(self.state, content, model=model)
        result.state = self.state
        return result
