#!/usr/bin/env python3
"""Multi-turn via one shared StateStore (no serialized model-to-model handoff)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "python"), str(ROOT)]

from models import register_builtins
from mom import Graph, ModelDirectory, Session, ping


def main() -> None:
    directory = ModelDirectory()
    register_builtins(directory)

    graph = (
        Graph()
        .add("router", "stub.decision")
        .add("fast", "stub.slm")
        .speculate("router", "fast")
    )

    # One store for the whole conversation
    session = Session(directory, graph)
    print(f"native: {ping()}  store_id={id(session.state)}")

    r1 = session.say("hi")
    r2 = session.say("what did I just say?")
    r3 = session.say("please reason carefully about turns")  # hard → may miss to llm

    print(f"turn1: {r1.output}")
    print(f"turn2: {r2.output}")
    print(f"turn3: {r3.output}")
    print(f"turns={session.turns}")
    print("messages (shared store):")
    for m in session.messages:
        print(f"  {m['role']}: {m.get('content', '')[:80]}")
    print(f"history lived in StateStore (not hop messages): {len(session.messages)} entries")


if __name__ == "__main__":
    main()
