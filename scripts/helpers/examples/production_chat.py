#!/usr/bin/env python3
"""
Production chat via real adapters (OpenAI-compatible local or cloud).
Requires a reachable backend. Default: Ollama at localhost:11434.
  cp .env.example .env   # edit as needed
  ollama pull llama3.2
  python scripts/helpers/examples/production_chat.py
  python scripts/helpers/examples/production_chat.py "explain MoM in one sentence"
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from mom import Session
from mom.config import Settings
from mom.logging_config import setup_logging
from mom.runtime import build_directory, build_registry, concurrency_limits


def main() -> None:
    settings = Settings.from_env()
    setup_logging(level=settings.log_level, json_logs=settings.log_json)
    directory = build_directory(settings)
    registry = build_registry(directory)
    spec = registry.pick(directory, settings.default_graph)
    session = Session(directory, spec.graph, limits=concurrency_limits(settings))
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Say hello in one short sentence."
    print(f"graph={spec.name} prefer_local={settings.prefer_local} model_endpoint={settings.chat_endpoint()[0]}")
    result = session.say(prompt)
    print(f"output: {result.output}")
    print(
        f"metrics: total={result.metrics.get('total_ms'):.1f}ms "
        f"spec={result.metrics.get('spec')} graph={result.metrics.get('graph')}"
    )


if __name__ == "__main__":
    main()
