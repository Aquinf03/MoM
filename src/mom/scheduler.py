"""Execute graphs with optional speculative route-then-run overlap.

Prefers native `run_graph` (planner + Trace timing) when the extension and a
mirrored native directory are available; otherwise falls back to pure Python.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from mom.bus import Bus
from mom.cancel import CancelToken, CancelledError
from mom.directory import ModelDirectory
from mom.graph import Graph
from mom.limits import ConcurrencyLimits, Limiter
from mom.prior import LightPrior, apply_prior_to_graph
from mom.state import StateStore

try:
    from mom._native import plan_graph as _plan_graph
    from mom._native import route_from as _route_from
    from mom._native import route_matches_prior as _route_matches_prior
    from mom._native import run_graph as _run_graph
except ImportError:
    _plan_graph = None
    _route_from = None
    _route_matches_prior = None
    _run_graph = None


def _py_plan_graph(graph: Graph) -> dict[str, Any]:
    """Pure-Python planner mirroring mom-core (fallback)."""
    nodes = {n.name: n for n in graph.nodes}
    priors: dict[str, str] = {}
    prior_nodes: set[str] = set()
    for e in graph.edges:
        if e.kind != "speculate":
            continue
        if e.frm in priors:
            raise ValueError(f"router '{e.frm}' has multiple speculate priors")
        for d in graph.edges:
            if d.kind == "depend" and d.frm == e.frm and d.to == e.to:
                raise ValueError(f"conflicting depend/speculate edges at '{e.to}'")
        priors[e.frm] = e.to
        prior_nodes.add(e.to)

    indeg = {n: 0 for n in nodes}
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for e in graph.edges:
        if e.kind != "depend":
            continue
        indeg[e.to] += 1
        adj[e.frm].append(e.to)

    order_index = {n.name: i for i, n in enumerate(graph.nodes)}
    ready = sorted((n for n, d in indeg.items() if d == 0), key=lambda n: order_index[n])
    topo: list[str] = []
    while ready:
        n = ready.pop(0)
        topo.append(n)
        nxt = []
        for c in adj[n]:
            indeg[c] -= 1
            if indeg[c] == 0:
                nxt.append(c)
        ready.extend(sorted(nxt, key=lambda x: order_index[x]))
        ready.sort(key=lambda x: order_index[x])
    if len(topo) != len(nodes):
        raise ValueError("depend edges contain a cycle")

    steps: list[dict[str, str]] = []
    done: set[str] = set()
    for name in topo:
        if name in done:
            continue
        if name in priors:
            prior = priors[name]
            steps.append({"type": "speculate", "router": name, "prior": prior})
            done.add(name)
            done.add(prior)
            continue
        if name in prior_nodes:
            continue
        steps.append({"type": "run", "node": name})
        done.add(name)
    return {"steps": steps}


def plan_graph(graph: Graph) -> dict[str, Any]:
    """Return execution steps for `graph` (native planner when available)."""
    if _plan_graph is not None:
        return _plan_graph(graph.to_dict())
    return _py_plan_graph(graph)


def route_from(value: Any) -> str | None:
    if _route_from is not None:
        return _route_from(value)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("route", "model", "node", "target"):
            if key in value and isinstance(value[key], str):
                return value[key]
    return None


def route_matches_prior(route: str, prior_name: str, prior_model_id: str) -> bool:
    if _route_matches_prior is not None:
        return _route_matches_prior(route, prior_name, prior_model_id)
    return route == prior_name or route == prior_model_id


@dataclass
class RunResult:
    """Output of one Scheduler.run / mom.run."""

    output: Any
    metrics: dict[str, Any] = field(default_factory=dict)
    state: StateStore | None = None


def _needs_wave_exec(graph: Graph) -> bool:
    """True when multiple roots or a join — needs shared-input fan-out."""
    nodes = {n.name for n in graph.nodes}
    parents: dict[str, list[str]] = {n: [] for n in nodes}
    for e in graph.edges:
        if e.kind != "depend":
            continue
        parents[e.to].append(e.frm)
    roots = [n for n, p in parents.items() if not p]
    joins = [n for n, p in parents.items() if len(p) > 1]
    return len(roots) > 1 or bool(joins)


def _candidate_record(out: Any, model_id: str) -> dict[str, Any]:
    if isinstance(out, dict):
        text = out.get("text", out)
        model = out.get("model", model_id)
        return {"model": model, "text": text if isinstance(text, str) else str(text)}
    return {"model": model_id, "text": str(out)}


class Scheduler:
    """Execute a graph against a model directory + shared state."""

    def __init__(
        self,
        directory: ModelDirectory,
        *,
        bus: Bus | None = None,
        limits: ConcurrencyLimits | Limiter | None = None,
        prior: LightPrior | None = None,
    ) -> None:
        self.directory = directory
        self.bus = bus or Bus.text_json()
        self.prior = prior
        if isinstance(limits, Limiter):
            self.limiter = limits
        elif isinstance(limits, ConcurrencyLimits):
            self.limiter = Limiter(limits)
        else:
            self.limiter = Limiter()

    def run(
        self,
        graph: Graph,
        input: Any,
        state: StateStore | None = None,
    ) -> RunResult:
        store = state or StateStore()
        with self.limiter.run_slot() as waited_ms:
            result = self._run_inner(graph, input, store)
            result.metrics = {
                **result.metrics,
                "limits": self.limiter.snapshot(),
                "run_waited_ms": waited_ms,
            }
            return result

    def _run_inner(
        self,
        graph: Graph,
        input: Any,
        store: StateStore,
    ) -> RunResult:
        active = graph
        suggested: str | None = None
        if self.prior is not None:
            suggested = self.prior.suggest(input, store)
            active = apply_prior_to_graph(graph, suggested)

        wave = _needs_wave_exec(active)
        # Embedding-bus / fan-out waves: Python path.
        use_native = (
            not wave
            and _run_graph is not None
            and self.directory.native is not None
            and type(store).__name__ == "StateStore"
            and self.bus.kind() != "embedding"
        )

        if use_native:
            bus = self.bus if type(self.bus).__name__ == "Bus" else None
            raw = _run_graph(
                active.to_dict(),
                input,
                self.directory.native,
                state=store,
                bus=bus,
            )
            metrics = dict(raw["metrics"])
            out_state = raw.get("state") or store
            result = RunResult(output=raw["output"], metrics=metrics, state=out_state)
        elif wave:
            result = self._run_python_waves(active, input, store)
        else:
            result = self._run_python(active, input, store)

        if self.prior is not None and suggested is not None:
            result.metrics["prior_suggested"] = suggested
            result.metrics["prior"] = self.prior.snapshot()
            winner = _winner_from_result(active, result)
            if winner is not None:
                # Feature from the pre-run store (native may return a twin).
                self.prior.observe(winner, input=input, state=store)
                result.metrics["prior_observed"] = winner
                result.metrics["prior"] = self.prior.snapshot()
        return result

    def _run_python(self, graph: Graph, input: Any, state: StateStore) -> RunResult:
        plan = plan_graph(graph)
        metrics: dict[str, Any] = {
            "node_ms": {},
            "spec": {},
            "overlap_saved_ms": 0.0,
            "critical_path_ms": 0.0,
            "spans": [],
        }
        t0 = time.perf_counter()
        current = input
        nodes = {n.name: n for n in graph.nodes}

        for step in plan["steps"]:
            if step["type"] == "run":
                current = self._run_node(nodes[step["node"]], current, state, metrics)
            elif step["type"] == "speculate":
                current = self._run_speculate(
                    graph,
                    router_name=step["router"],
                    prior_name=step["prior"],
                    input=current,
                    state=state,
                    metrics=metrics,
                )
            else:
                raise ValueError(f"unknown step type: {step['type']}")

        total = (time.perf_counter() - t0) * 1000.0
        metrics["total_ms"] = total
        metrics["orchestration_overhead_ms"] = max(
            0.0, total - float(metrics["critical_path_ms"])
        )
        metrics["router_ms"] = sum(
            s["duration_ms"] for s in metrics["spans"] if s.get("kind") == "router"
        )
        metrics["model_ms"] = sum(
            s["duration_ms"] for s in metrics["spans"] if s.get("kind") == "model"
        )
        state.set("mom.metrics", metrics)
        return RunResult(output=current, metrics=metrics, state=state)

    def _run_python_waves(
        self, graph: Graph, input: Any, state: StateStore
    ) -> RunResult:
        """Fan-out / join executor: siblings share parent input; join sees candidates."""
        metrics: dict[str, Any] = {
            "node_ms": {},
            "spec": {},
            "overlap_saved_ms": 0.0,
            "critical_path_ms": 0.0,
            "spans": [],
            "waves": [],
        }
        t0 = time.perf_counter()
        nodes = {n.name: n for n in graph.nodes}
        parents: dict[str, list[str]] = {n: [] for n in nodes}
        for e in graph.edges:
            if e.kind != "depend":
                continue
            parents[e.to].append(e.frm)

        # If the graph also has speculate edges, fall back to linear plan for those
        # (wave path is for fan-out/join). Mixed speculate+fanout is v2+.
        if any(e.kind == "speculate" for e in graph.edges):
            return self._run_python(graph, input, state)

        outputs: dict[str, Any] = {}
        done: set[str] = set()
        last: Any = input

        def ready_nodes() -> list[str]:
            return sorted(
                n for n in nodes if n not in done and all(p in done for p in parents[n])
            )

        while True:
            wave = ready_nodes()
            if not wave:
                break
            metrics["waves"].append(
                {"type": "parallel" if len(wave) > 1 else "run", "nodes": list(wave)}
            )

            def input_for(name: str) -> Any:
                pars = parents[name]
                if not pars:
                    return input
                if len(pars) == 1:
                    return outputs[pars[0]]
                return input  # join: reconcile reads state['candidates']

            if len(wave) == 1:
                name = wave[0]
                out = self._run_node(nodes[name], input_for(name), state, metrics)
                outputs[name] = out
                last = out
                done.add(name)
                continue

            # Parallel fan-out — critical path advances by max(node_ms).
            shared = input
            # Prefer shared parent output when all siblings share one parent.
            p0 = parents[wave[0]]
            if p0 and all(parents[n] == p0 for n in wave):
                shared = outputs[p0[0]] if len(p0) == 1 else input
            elif all(not parents[n] for n in wave):
                shared = input

            def run_one(name: str) -> tuple[str, Any, float]:
                node = nodes[name]
                model = self.directory.create(node.model_id)
                value = self._bus_hop(shared, metrics)
                with self.limiter.model_slot():
                    t1 = time.perf_counter()
                    try:
                        out = model.run(value, state, cancel=None)
                    except TypeError:
                        out = model.run(value, state)
                    ms = (time.perf_counter() - t1) * 1000.0
                return name, out, ms

            with ThreadPoolExecutor(max_workers=len(wave)) as pool:
                results = list(pool.map(run_one, wave))

            wave_ms = 0.0
            cands = []
            for name, out, ms in results:
                outputs[name] = out
                metrics["node_ms"][name] = ms
                metrics["spans"].append(
                    {"name": name, "kind": "model", "duration_ms": ms}
                )
                wave_ms = max(wave_ms, ms)
                cands.append(_candidate_record(out, nodes[name].model_id))
                last = out
                done.add(name)
            metrics["critical_path_ms"] += wave_ms
            metrics["overlap_saved_ms"] += max(
                0.0, sum(metrics["node_ms"][n] for n in wave) - wave_ms
            )
            state.set("candidates", cands)

        if len(done) != len(nodes):
            missing = sorted(set(nodes) - done)
            raise ValueError(f"wave exec stuck; unfinished nodes: {missing}")

        total = (time.perf_counter() - t0) * 1000.0
        metrics["total_ms"] = total
        metrics["orchestration_overhead_ms"] = max(
            0.0, total - float(metrics["critical_path_ms"])
        )
        metrics["router_ms"] = sum(
            s["duration_ms"] for s in metrics["spans"] if s.get("kind") == "router"
        )
        metrics["model_ms"] = sum(
            s["duration_ms"] for s in metrics["spans"] if s.get("kind") == "model"
        )
        state.set("mom.metrics", metrics)
        return RunResult(output=last, metrics=metrics, state=state)

    def _bus_hop(self, value: Any, metrics: dict[str, Any] | None = None) -> Any:
        """Encode/decode through the hop bus; embedding packs only float vectors."""
        kind = self.bus.kind()
        if kind == "embedding":
            is_vec = (
                isinstance(value, (list, tuple))
                and (len(value) == 0 or isinstance(value[0], (int, float)))
            )
            if not is_vec:
                # Text ingress / non-vector: do not mandate embedding packing.
                return value
        t0 = time.perf_counter()
        out = self.bus.decode(self.bus.encode(value))
        ms = (time.perf_counter() - t0) * 1000.0
        if metrics is not None:
            metrics.setdefault("bus_ms", 0.0)
            metrics["bus_ms"] = float(metrics["bus_ms"]) + ms
            metrics.setdefault("bus_hops", 0)
            metrics["bus_hops"] = int(metrics["bus_hops"]) + 1
            metrics["bus_kind"] = kind
        return out

    def _run_node(
        self,
        node: Any,
        input: Any,
        state: StateStore,
        metrics: dict[str, Any],
    ) -> Any:
        model = self.directory.create(node.model_id)
        value = self._bus_hop(input, metrics)
        with self.limiter.model_slot():
            t0 = time.perf_counter()
            try:
                out = model.run(value, state, cancel=None)
            except TypeError:
                out = model.run(value, state)
            ms = (time.perf_counter() - t0) * 1000.0
        kind = (
            "router"
            if "router" in self.directory.get(node.model_id).tags
            else "model"
        )
        metrics["node_ms"][node.name] = ms
        metrics["critical_path_ms"] += ms
        metrics["spans"].append(
            {"name": node.name, "kind": kind, "duration_ms": ms}
        )
        return out

    def _run_speculate(
        self,
        graph: Graph,
        *,
        router_name: str,
        prior_name: str,
        input: Any,
        state: StateStore,
        metrics: dict[str, Any],
    ) -> Any:
        router_node = graph.node(router_name)
        prior_node = graph.node(prior_name)
        router_model = self.directory.create(router_node.model_id)
        prior_model = self.directory.create(prior_node.model_id)

        value = self._bus_hop(input, metrics)
        cancel = CancelToken()

        def run_router() -> tuple[Any, float]:
            with self.limiter.model_slot():
                t0 = time.perf_counter()
                out = router_model.run(value, state, cancel=None)
                return out, (time.perf_counter() - t0) * 1000.0

        def run_prior() -> tuple[Any, float]:
            with self.limiter.model_slot():
                t0 = time.perf_counter()
                try:
                    out = prior_model.run(value, state, cancel=cancel)
                except CancelledError:
                    ms = (time.perf_counter() - t0) * 1000.0
                    return ("__cancelled__", ms)
                return out, (time.perf_counter() - t0) * 1000.0

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_prior = pool.submit(run_prior)
            route_out, router_ms = run_router()

            route = route_from(route_out)
            if route is None:
                cancel.cancel()
                fut_prior.result()
                raise ValueError(f"router '{router_name}' did not return a route")

            hit = route_matches_prior(route, prior_name, prior_node.model_id)
            if not hit:
                # Miss: stop speculative loser before waiting on it.
                cancel.cancel()

            prior_out, prior_ms = fut_prior.result()

        cancelled = prior_out == "__cancelled__"
        metrics["node_ms"][router_name] = router_ms
        metrics["node_ms"][prior_name] = prior_ms
        wall = max(router_ms, prior_ms)
        metrics["critical_path_ms"] += wall
        if not cancelled:
            metrics["overlap_saved_ms"] += min(router_ms, prior_ms)
        else:
            metrics["prior_cancelled"] = True
            metrics["prior_cancelled_ms"] = prior_ms
        metrics["spans"].extend(
            [
                {"name": router_name, "kind": "router", "duration_ms": router_ms},
                {
                    "name": prior_name,
                    "kind": "model",
                    "duration_ms": prior_ms,
                    "cancelled": cancelled,
                },
                {
                    "name": f"{router_name}+{prior_name}",
                    "kind": "speculate_wall",
                    "duration_ms": wall,
                },
            ]
        )

        if hit:
            metrics["spec"][router_name] = "hit"
            if cancelled:
                raise RuntimeError("speculative prior cancelled on hit path")
            return prior_out

        metrics["spec"][router_name] = "miss"
        target = self._resolve_route(graph, route)
        return self._run_node(target, value, state, metrics)

    def _resolve_route(self, graph: Graph, route: str) -> Any:
        for n in graph.nodes:
            if n.name == route or n.model_id == route:
                return n
        if route not in self.directory:
            raise KeyError(f"route '{route}' not in graph or directory")
        from mom.graph import Node

        return Node(name=route, model_id=route)


def _winner_from_result(graph: Graph, result: RunResult) -> str | None:
    """Best-effort actual winner (model id) after a speculative hop."""
    spec = result.metrics.get("spec") or {}
    if not spec:
        return None
    # Prefer model id on the final output when present.
    out = result.output
    if isinstance(out, dict) and isinstance(out.get("model"), str):
        return out["model"]
    # Fall back: on hit use speculated node’s model; on miss use route if known.
    for router_name, outcome in spec.items():
        pairs = [(e.frm, e.to) for e in graph.edges if e.kind == "speculate"]
        prior_name = next((p for r, p in pairs if r == router_name), None)
        if prior_name is None:
            continue
        if outcome == "hit":
            try:
                return graph.node(prior_name).model_id
            except KeyError:
                return prior_name
    return None


def run(
    graph: Graph,
    input: Any,
    directory: ModelDirectory,
    *,
    state: StateStore | None = None,
    bus: Bus | None = None,
    limits: ConcurrencyLimits | Limiter | None = None,
    prior: LightPrior | None = None,
) -> RunResult:
    """Single external call — feels like one model."""
    return Scheduler(directory, bus=bus, limits=limits, prior=prior).run(
        graph, input, state
    )


def run_named(
    name: str | None,
    input: Any,
    directory: ModelDirectory,
    registry: Any,
    *,
    state: StateStore | None = None,
    bus: Bus | None = None,
    limits: ConcurrencyLimits | Limiter | None = None,
    prior: LightPrior | None = None,
    selector: Any = None,
) -> RunResult:
    """Pick a graph from the registry (by name or selector) and run it."""
    from mom.select import heuristic_select

    spec = registry.pick(
        directory,
        name,
        selector=selector or (heuristic_select if name is None else None),
        input=input,
        state=state,
    )
    result = run(
        spec.graph,
        input,
        directory,
        state=state,
        bus=bus,
        limits=limits,
        prior=prior,
    )
    result.metrics = {
        **result.metrics,
        "graph": spec.name,
        "shape": spec.shape,
        "latency_hideable": spec.latency_hideable,
    }
    return result

