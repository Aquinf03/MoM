"""Colocated router — heuristic first; optional local LM for ambiguous cases."""

from __future__ import annotations

from typing import Any

from mom.adapters.local_chat import LocalChatModel
from mom.cancel import CancelToken
from mom.config import Settings
from mom.state import StateStore
from mom.util_text import as_text_light


class LocalRouterModel:
    """
    Pick a directory id for the next hop.

    Default is pure heuristic (no weights). Set `source` to a Hub id / path
    to ask a small local LM when the heuristic is unsure.
    """

    def __init__(
        self,
        *,
        candidates: tuple[str, ...] = ("prod.chat.fast", "prod.chat.strong"),
        settings: Settings | None = None,
        model_id: str = "local.router",
        default_route: str | None = None,
        source: str | None = None,
        engine: Any = None,
    ) -> None:
        self.candidates = candidates
        self.settings = settings or Settings.from_env()
        self.model_id = model_id
        self.default_route = default_route or candidates[0]
        self.source = source
        self._chat: LocalChatModel | None = None
        if source:
            self._chat = LocalChatModel(
                source,
                settings=self.settings,
                model_id=model_id,
                system=(
                    "You are a router. Reply with ONLY one of these exact ids, nothing else:\n"
                    + "\n".join(candidates)
                ),
                engine=engine,
                max_new_tokens=8,
            )

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        forced = state.get("route")
        if isinstance(forced, str) and forced:
            return {"route": forced, "reason": "state", "model": self.model_id}

        label = state.get("classification")
        text = as_text_light(input)
        if label == "hard" or "reason carefully" in text.lower() or len(text) > 400:
            route = self.candidates[-1] if len(self.candidates) > 1 else self.default_route
            return {"route": route, "reason": "heuristic", "model": self.model_id}
        if label == "easy" or len(text) < 40:
            return {"route": self.default_route, "reason": "heuristic", "model": self.model_id}

        if self._chat is None:
            return {"route": self.default_route, "reason": "heuristic", "model": self.model_id}

        out = self._chat.run(input, state, cancel=cancel)
        raw = (out.get("text") or "").strip().split()[0] if isinstance(out, dict) else str(out)
        route = raw if raw in self.candidates else self.default_route
        return {"route": route, "reason": "model", "raw": raw, "model": self.model_id}
