#!/usr/bin/env python3
"""Speculative route-then-run demo: router overlaps with likely generator."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "python"), str(ROOT)]

from models import register_builtins
from mom import Graph, ModelDirectory, Scheduler, StateStore, ping


def main() -> None:
    directory = ModelDirectory()
    register_builtins(directory)

    graph = (
        Graph()
        .add("router", "stub.router")
        .add("gen", "stub.echo")
        .speculate("router", "gen")
    )

    sched = Scheduler(directory)

    # Hit path: route matches speculative prior
    state_hit = StateStore()
    state_hit.set("route", "stub.echo")
    hit = sched.run(graph, "hello hit", state_hit)

    # Miss path: router picks alt model
    state_miss = StateStore()
    state_miss.set("route", "stub.echo_alt")
    miss = sched.run(graph, "hello miss", state_miss)

    print(f"native ping: {ping()}")
    print(f"plan: {graph.to_dict()}")
    print(f"HIT  output={hit.output!r} spec={hit.metrics.get('spec')} total_ms={hit.metrics['total_ms']:.1f}")
    print(f"     node_ms={hit.metrics['node_ms']} overlap_saved_ms={hit.metrics['overlap_saved_ms']:.1f}")
    print(f"     trace={state_hit.get('trace')}")
    print(f"MISS output={miss.output!r} spec={miss.metrics.get('spec')} total_ms={miss.metrics['total_ms']:.1f}")
    print(f"     node_ms={miss.metrics['node_ms']} overlap_saved_ms={miss.metrics['overlap_saved_ms']:.1f}")
    print(f"     trace={state_miss.get('trace')}")


if __name__ == "__main__":
    main()
