"""The thing you build products with.

MoM is not a chatbot and not a model zoo. It is the composition runtime:
register any models, wire graphs, call one surface that feels like a single model.

    from mom import MoM

    app = MoM()                    # loads env, production adapters, default graph
    print(app.chat("hello").text)  # multi-turn session baked in

    app.register("billing.tool", MyTool, tags={"tool"})
    app.add_graph("support", my_graph, requires=["billing.tool", "prod.chat.fast"])
    print(app.run("refund please", graph="support").output)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mom.adapter import Model
from mom.config import Settings
from mom.directory import ModelDirectory, ModelFactory
from mom.graph import Graph
from mom.health import health_check, readiness_check
from mom.limits import ConcurrencyLimits, Limiter
from mom.logging_config import setup_logging
from mom.prior import LightPrior
from mom.registry import GraphRegistry, GraphSpec
from mom.runtime import build_directory, build_registry, concurrency_limits
from mom.scheduler import RunResult, run, run_named
from mom.session import Session
from mom.state import StateStore


@dataclass
class ChatReply:
    """Normalized chat result for app code."""

    text: str
    output: Any
    metrics: dict[str, Any]
    model: str | None = None
    raw: RunResult | None = None

    @property
    def total_ms(self) -> float:
        return float(self.metrics.get("total_ms") or 0.0)


class MoM:
    """
    Application handle — directory + registry + limits + default session.

    This is the SDK surface for building full products. Lower layers
    (`Scheduler`, `Graph`, adapters) stay available when you need them.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        directory: ModelDirectory | None = None,
        registry: GraphRegistry | None = None,
        graph: str | Graph | None = None,
        limits: ConcurrencyLimits | Limiter | None = None,
        prior: LightPrior | None = None,
        load_production: bool = True,
    ) -> None:
        self.settings = settings or Settings.from_env()
        setup_logging(level=self.settings.log_level, json_logs=self.settings.log_json)

        if directory is not None:
            self.directory = directory
        elif load_production:
            self.directory = build_directory(self.settings)
        else:
            self.directory = ModelDirectory()

        if registry is not None:
            self.registry = registry
        elif load_production:
            self.registry = build_registry(self.directory)
        else:
            self.registry = GraphRegistry()
        if limits is None:
            self.limits: ConcurrencyLimits | Limiter = concurrency_limits(self.settings)
        else:
            self.limits = limits
        self.prior = prior

        if isinstance(graph, Graph):
            self._default_graph_obj: Graph | None = graph
            self.default_graph_name = self.settings.default_graph
        else:
            self._default_graph_obj = None
            self.default_graph_name = graph or self.settings.default_graph

        self._session: Session | None = None

    # --- catalog / topology (how you extend MoM into your product) ---

    def register(
        self,
        id: str,
        factory: ModelFactory | type,
        *,
        tags: set[str] | frozenset[str] | None = None,
        **meta: Any,
    ) -> MoM:
        """Register any model kind. Your product’s tools/LLMs/retrievers go here."""
        fn: ModelFactory
        if isinstance(factory, type):
            cls = factory

            def fn() -> Model:
                return cls()  # type: ignore[return-value]
        else:
            fn = factory
        self.directory.register(id, fn, tags=tags, **meta)
        return self

    def add_graph(
        self,
        name: str,
        graph: Graph,
        *,
        shape: str = "custom",
        requires: set[str] | frozenset[str] | None = None,
        latency_hideable: bool = False,
        description: str = "",
        tags: set[str] | frozenset[str] | None = None,
    ) -> MoM:
        """Register a named topology your product can select at call time."""
        req = frozenset(requires or {n.model_id for n in graph.nodes})
        self.registry.register(
            GraphSpec(
                name=name,
                graph=graph,
                shape=shape,
                requires=req,
                latency_hideable=latency_hideable,
                description=description or name,
                tags=frozenset(tags or ()),
            )
        )
        return self

    def model(self, id: str, **meta: Any) -> Callable[[type], type]:
        """Decorator: `@app.model("my.id", tags={"tool"})` on a class with `run`."""

        def deco(cls: type) -> type:
            tags = meta.pop("tags", None)
            self.register(id, cls, tags=tags, **meta)
            return cls

        return deco

    # --- call surface (what your product exposes to users) ---

    def session(self, *, graph: str | Graph | None = None, fresh: bool = False) -> Session:
        """Multi-turn conversation over shared StateStore."""
        if fresh or self._session is None or graph is not None:
            g = self._resolve_graph(graph)
            self._session = Session(
                self.directory,
                g,
                limits=self.limits,
                prior=self.prior,
            )
        return self._session

    def chat(self, message: str, *, graph: str | Graph | None = None) -> ChatReply:
        """One user turn on the default (or named) session — build chat products on this."""
        sess = self.session(graph=graph)
        result = sess.say(message)
        text, model = _text_model(result.output)
        return ChatReply(
            text=text,
            output=result.output,
            metrics=result.metrics,
            model=model,
            raw=result,
        )

    def run(
        self,
        input: Any,
        *,
        graph: str | Graph | None = None,
        state: StateStore | None = None,
    ) -> RunResult:
        """Single-shot composition (no session history). Build pipelines / tools on this."""
        gname_or_obj = graph if graph is not None else self.default_graph_name
        if isinstance(gname_or_obj, Graph) or self._default_graph_obj is not None and graph is None:
            g = gname_or_obj if isinstance(gname_or_obj, Graph) else self._default_graph_obj
            assert g is not None
            return run(
                g,
                input,
                self.directory,
                state=state,
                limits=self.limits,
                prior=self.prior,
            )
        name = gname_or_obj if isinstance(gname_or_obj, str) else self.default_graph_name
        return run_named(
            name,
            input,
            self.directory,
            self.registry,
            state=state,
            limits=self.limits,
            prior=self.prior,
        )

    def health(self) -> dict[str, Any]:
        return health_check(self.directory, self.settings)

    def ready(self, *, probe: bool = True) -> dict[str, Any]:
        return readiness_check(self.directory, self.settings, probe_local=probe)

    def serve(self) -> None:
        """Run the HTTP API (`/v1/run`, `/v1/chat`, `/health`, `/ready`)."""
        from mom.server import main as serve_main

        serve_main()

    def _resolve_graph(self, graph: str | Graph | None) -> Graph:
        if isinstance(graph, Graph):
            return graph
        if graph is None and self._default_graph_obj is not None:
            return self._default_graph_obj
        name = graph or self.default_graph_name
        return self.registry.pick(self.directory, name).graph


def _text_model(output: Any) -> tuple[str, str | None]:
    if isinstance(output, dict):
        text = output.get("text")
        model = output.get("model")
        if isinstance(text, str):
            return text, model if isinstance(model, str) else None
        return str(output), model if isinstance(model, str) else None
    return str(output), None
