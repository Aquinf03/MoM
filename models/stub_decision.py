"""Decision / reconcile stubs — route or merge multi-model outputs."""

from __future__ import annotations

from typing import Any

from models._util import append_trace, as_text, sleep_ms
from mom.directory import ModelDirectory
from mom.state import StateStore


class DecisionModel:
    """
    Decision stub (routing-oriented).

    Picks `stub.slm` vs `stub.llm` from classification / text heuristics.
    Heavier than classifier (~15ms) but still not a full reconcile.
    """

    def __init__(self, delay_ms: float = 15.0) -> None:
        self.delay_ms = delay_ms

    def run(self, input: Any, state: StateStore) -> Any:
        sleep_ms(self.delay_ms)
        label = state.get("classification")
        text = as_text(input).lower()
        if label == "hard" or "reason" in text or len(text) > 80:
            route = "stub.llm"
        else:
            route = "stub.slm"
        append_trace(state, f"stub.decision->{route}")
        return {"route": route, "reason": label or "heuristic"}


class ReconcileModel:
    """
    Reconcile stub — merges multiple candidate texts in state.

    Expects `state['candidates']` as a list of `{model, text}` dicts.
    Cannot be fully latency-hidden (serial merge); tagged accordingly.
    """

    def __init__(self, delay_ms: float = 25.0) -> None:
        self.delay_ms = delay_ms

    def run(self, input: Any, state: StateStore) -> Any:
        sleep_ms(self.delay_ms)
        candidates = state.get("candidates") or []
        if not isinstance(candidates, list):
            candidates = list(candidates)
        if not candidates:
            text = as_text(input)
            sources = []
        else:
            parts = []
            sources = []
            for c in candidates:
                if isinstance(c, dict):
                    parts.append(str(c.get("text", c)))
                    sources.append(c.get("model", "unknown"))
                else:
                    parts.append(str(c))
            text = " | ".join(parts)
        append_trace(state, "stub.reconcile")
        return {
            "text": f"[reconciled] {text}",
            "sources": sources,
            "model": "stub.reconcile",
        }


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.decision",
        lambda: DecisionModel(),
        tags={"stub", "decision", "router"},
        latency_class="medium",
        modality="text",
    )
    directory.register(
        "stub.reconcile",
        lambda: ReconcileModel(),
        tags={"stub", "reconcile", "decision"},
        latency_class="medium",
        modality="text",
        latency_hideable=False,
    )
