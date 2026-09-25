"""Multi-turn session — one StateStore reused across runs."""

from __future__ import annotations

from typing import Any

from mom.bus import Bus
from mom.directory import ModelDirectory
from mom.graph import Graph
from mom.scheduler import RunResult, run
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
    """

    def __init__(
        self,
        directory: ModelDirectory,
        graph: Graph,
        *,
        state: StateStore | None = None,
        bus: Bus | None = None,
    ) -> None:
        self.directory = directory
        self.graph = graph
        self.state = state or StateStore()
        self.bus = bus

    @property
    def messages(self) -> list[dict[str, Any]]:
        return get_messages(self.state)

    @property
    def turns(self) -> int:
        return turn_count(self.state)

    def say(self, text: str) -> RunResult:
        """One user turn against the shared store + graph."""
        add_user(self.state, text)
        result = run(
            self.graph,
            text,
            self.directory,
            state=self.state,
            bus=self.bus,
        )
        # Native run may return a twin StateStore handle that holds the writes.
        if result.state is not None:
            self.state = result.state
        content, model = _assistant_content(result.output)
        add_assistant(self.state, content, model=model)
        result.state = self.state
        return result
