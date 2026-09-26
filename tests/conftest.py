"""Shared fixtures for production-grade SDK tests (installed `mom`, no path hacks)."""

from __future__ import annotations

import pytest

from mom import (
    ConcurrencyLimits,
    Graph,
    GraphRegistry,
    Limiter,
    ModelDirectory,
    StateStore,
    register_builtin_shapes,
)


class Echo:
    def __init__(self, tag: str = "echo", delay_ms: float = 5.0) -> None:
        self.tag = tag
        self.delay_ms = delay_ms

    def run(self, input, state, cancel=None):
        from mom.cancel import sleep_ms

        sleep_ms(self.delay_ms, cancel)
        text = input if isinstance(input, str) else str(input)
        if isinstance(input, dict) and "text" in input:
            text = str(input["text"])
        state.set("last", self.tag)
        return {"text": text, "model": self.tag}


class SlowEcho(Echo):
    def __init__(self) -> None:
        super().__init__(tag="slow", delay_ms=40.0)


class Router:
    def __init__(self, default: str = "fast") -> None:
        self.default = default

    def run(self, input, state, cancel=None):
        from mom.cancel import sleep_ms

        sleep_ms(8.0, cancel)
        route = state.get("route") or self.default
        return {"route": route}


class LLMish(Echo):
    def __init__(self) -> None:
        super().__init__(tag="llm", delay_ms=50.0)


class Reconcile:
    def run(self, input, state, cancel=None):
        from mom.cancel import sleep_ms

        sleep_ms(10.0, cancel)
        cands = state.get("candidates") or []
        texts = []
        sources = []
        for c in cands if isinstance(cands, list) else []:
            if isinstance(c, dict):
                texts.append(str(c.get("text", c)))
                sources.append(c.get("model", "?"))
        return {
            "text": " | ".join(texts) if texts else str(input),
            "sources": sources,
            "model": "reconcile",
        }


@pytest.fixture
def directory() -> ModelDirectory:
    d = ModelDirectory()
    d.register("fast", lambda: Echo("fast", 15.0), tags={"generator"})
    d.register("slow", SlowEcho, tags={"generator"})
    d.register("llm", LLMish, tags={"generator", "llm"})
    d.register("router", lambda: Router("fast"), tags={"router"})
    d.register("reconcile", Reconcile, tags={"reconcile"})
    return d


@pytest.fixture
def speculate_graph() -> Graph:
    return (
        Graph()
        .add("router", "router")
        .add("gen", "fast")
        .speculate("router", "gen")
    )


@pytest.fixture
def store() -> StateStore:
    return StateStore()
