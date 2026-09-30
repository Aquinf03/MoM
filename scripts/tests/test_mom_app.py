"""MoM() facade — the API you build products on."""

from __future__ import annotations

from mom import Graph, MoM, StateStore
from mom.config import Settings


class Echo:
    def __init__(self, tag: str = "echo") -> None:
        self.tag = tag

    def run(self, input, state, cancel=None):
        text = input if isinstance(input, str) else str(input)
        if isinstance(input, dict) and "text" in input:
            text = str(input["text"])
        return {"text": f"[{self.tag}] {text}", "model": self.tag}


class Router:
    def run(self, input, state, cancel=None):
        return {"route": "app.fast"}


def test_mom_register_graph_chat_run():
    settings = Settings(prefer_local=True, default_graph="demo")
    app = MoM(settings, load_production=False)
    app.register("app.fast", lambda: Echo("fast"), tags={"generator"})
    app.register("app.router", Router, tags={"router"})
    g = (
        Graph()
        .add("router", "app.router")
        .add("gen", "app.fast")
        .speculate("router", "gen")
    )
    app.add_graph("demo", g, requires={"app.router", "app.fast"}, latency_hideable=True)
    app.default_graph_name = "demo"

    reply = app.chat("hello")
    assert "hello" in reply.text
    assert reply.model == "fast"
    assert app.session().turns == 1

    r2 = app.chat("again")
    assert app.session().turns == 2
    assert "again" in r2.text

    one_shot = app.run("ping", graph="demo", state=StateStore())
    assert one_shot.output["model"] == "fast"

    h = app.health()
    assert h["models"] >= 2


def test_mom_decorator_register():
    app = MoM(Settings(), load_production=False)

    @app.model("app.decorated", tags={"tool"})
    class Tool:
        def run(self, input, state, cancel=None):
            return {"text": "ok", "model": "app.decorated"}

    assert "app.decorated" in app.directory
    out = app.directory.create("app.decorated").run("x", StateStore())
    assert out["text"] == "ok"
