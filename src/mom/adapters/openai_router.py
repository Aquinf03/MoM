"""Cheap router using a small chat model — returns route target ids."""

from __future__ import annotations

from typing import Any

from mom.adapters.openai_chat import OpenAIChatModel
from mom.cancel import CancelToken
from mom.config import Settings
from mom.state import StateStore
from mom.util_text import as_text_light


class OpenAIRouterModel:
    """
    Asks an LLM to pick between candidate model ids.

    Not latency-free — keep the underlying model small/local. Prefer
    heuristic/classifier stubs only for benches; this is the production router.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        candidates: tuple[str, ...] = ("prod.chat.fast", "prod.chat.strong"),
        settings: Settings | None = None,
        model_id: str = "openai.router",
        default_route: str | None = None,
    ) -> None:
        self.chat = OpenAIChatModel(
            base_url=base_url,
            api_key=api_key,
            model=model,
            settings=settings,
            model_id=model_id,
            system=(
                "You are a router. Reply with ONLY one of these exact ids, nothing else:\n"
                + "\n".join(candidates)
            ),
        )
        self.candidates = candidates
        self.model_id = model_id
        self.default_route = default_route or candidates[0]

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        # Allow forced route via state for tests / ops
        forced = state.get("route")
        if isinstance(forced, str) and forced:
            return {"route": forced, "reason": "state"}
        label = state.get("classification")
        text = as_text_light(input)
        # Cheap heuristic short-circuit before paying for a model call
        if label == "hard" or "reason carefully" in text.lower() or len(text) > 400:
            route = self.candidates[-1] if len(self.candidates) > 1 else self.default_route
            return {"route": route, "reason": "heuristic"}
        if label == "easy" or len(text) < 40:
            return {"route": self.default_route, "reason": "heuristic"}

        out = self.chat.run(input, state, cancel=cancel)
        raw = (out.get("text") or "").strip().split()[0] if isinstance(out, dict) else str(out)
        route = raw if raw in self.candidates else self.default_route
        return {"route": route, "reason": "model", "raw": raw}
