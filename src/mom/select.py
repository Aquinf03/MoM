"""Heuristic meta-layer: pick a graph name from directory + input/state.

Not a learned policy — cheap rules after the demo path (§6) already passes.
Prefer latency-hideable shapes when the prompt looks like chat.
"""

from __future__ import annotations

from typing import Any

from mom.directory import ModelDirectory
from mom.registry import GraphRegistry
from mom.util_text import as_text_light


def heuristic_select(
    registry: GraphRegistry,
    directory: ModelDirectory,
    input: Any = None,
    state: Any = None,
) -> str:
    """
    Choose an available graph name.

    Rules (first match among *available* graphs):
    - image-ish input → vision_caption
    - embed/similar keywords → embed_score
    - explicit reconcile / multi-view → fanout_reconcile
    - transform/reverse keywords → pipeline_transform
    - hard / long / reason → speculate_chat (hideable) else route_serial
    - default → speculate_chat if available, else first hideable, else first
    """
    avail = {s.name: s for s in registry.available(directory)}
    if not avail:
        raise KeyError("no graphs available for heuristic selection")

    text = as_text_light(input).lower()
    label = None
    if state is not None:
        try:
            label = state.get("classification")
        except Exception:
            label = None

    def have(*names: str) -> str | None:
        for n in names:
            if n in avail:
                return n
        return None

    if isinstance(input, dict) and ("image" in input or "image_url" in input):
        pick = have("vision_caption")
        if pick:
            return pick

    if any(k in text for k in ("embed", "similar", "nearest", "knn")):
        pick = have("embed_score")
        if pick:
            return pick

    if any(k in text for k in ("reconcile", "both models", "fan-out", "fanout", "merge views")):
        pick = have("fanout_reconcile")
        if pick:
            return pick

    if any(k in text for k in ("reverse", "transform", "flip")):
        pick = have("pipeline_transform")
        if pick:
            return pick

    hard = (
        label == "hard"
        or "reason" in text
        or len(text) > 80
    )
    if hard or text:
        pick = have("speculate_chat", "route_serial")
        if pick:
            return pick

    pick = have("speculate_chat")
    if pick:
        return pick
    hideable = [s.name for s in avail.values() if s.latency_hideable]
    if hideable:
        return sorted(hideable)[0]
    return sorted(avail)[0]


# Back-compat alias used by GraphRegistry.pick(selector=...)
select_graph = heuristic_select
