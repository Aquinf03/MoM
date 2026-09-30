"""Light prior for speculative “likely winner” selection.

Starts from a static default (graph speculate edge), then shifts toward
whatever has been winning — optionally bucketed by a cheap state feature
(e.g. classifier label). Not a second router: just frequency counts.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable


FeatureFn = Callable[[Any, Any], str]


def _default_feature(input: Any, state: Any, key: str | None) -> str:
    if key and state is not None:
        try:
            val = state.get(key)
        except Exception:
            val = None
        if val is not None and val != "":
            return str(val)
    if isinstance(input, str):
        return "long" if len(input) > 80 else "short"
    return "_"


@dataclass
class LightPrior:
    """
    Static default → learned frequency prior over candidate winners.

    `candidates` are node names and/or model ids the graph can speculate.
    After enough observations in a feature bucket, `suggest` returns the
    mode; until then it returns `default` (the static graph prior).
    """

    default: str
    candidates: tuple[str, ...] = ()
    feature_key: str | None = "classification"
    min_observations: int = 3
    feature_fn: FeatureFn | None = None
    _counts: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(dict))
    _total: int = 0

    def __post_init__(self) -> None:
        cands = tuple(self.candidates) if self.candidates else (self.default,)
        if self.default not in cands:
            cands = (self.default, *cands)
        self.candidates = cands

    def _feat(self, input: Any, state: Any) -> str:
        if self.feature_fn is not None:
            return self.feature_fn(input, state)
        return _default_feature(input, state, self.feature_key)

    def suggest(self, input: Any = None, state: Any = None) -> str:
        """Pick likely winner for this hop (default until warm)."""
        feat = self._feat(input, state)
        bucket = self._counts.get(feat) or {}
        n = sum(bucket.get(c, 0) for c in self.candidates)
        if n < self.min_observations:
            return self.default
        # Tie-break away from the static default once the bucket is warm.
        return max(
            self.candidates,
            key=lambda c: (bucket.get(c, 0), c != self.default),
        )

    def observe(self, winner: str, *, input: Any = None, state: Any = None) -> None:
        """Record the actual route/winner after a speculative hop."""
        if winner not in self.candidates:
            # Still learn aliases that match a candidate prefix / exact later resolve
            if not any(winner == c or winner.endswith(c) or c.endswith(winner) for c in self.candidates):
                # Accept unknown winners into candidate set only if they look like ids
                pass
        feat = self._feat(input, state)
        bucket = self._counts.setdefault(feat, {})
        key = winner if winner in self.candidates else self._alias(winner)
        if key is None:
            return
        bucket[key] = bucket.get(key, 0) + 1
        self._total += 1

    def _alias(self, winner: str) -> str | None:
        for c in self.candidates:
            if c == winner or c.endswith(winner) or winner.endswith(c):
                return c
        return None

    def snapshot(self) -> dict[str, Any]:
        return {
            "default": self.default,
            "candidates": list(self.candidates),
            "min_observations": self.min_observations,
            "total": self._total,
            "counts": {k: dict(v) for k, v in self._counts.items()},
        }


def apply_prior_to_graph(graph: Any, suggestion: str) -> Any:
    """
    Return a copy of `graph` with the speculative prior’s model_id set to
    `suggestion` (model id or node name). Keeps a single prior node so other
    catalog candidates are not scheduled as free roots.
    """
    from mom.graph import Edge, Graph

    prior_names = {e.to for e in graph.edges if e.kind == "speculate"}

    def model_for(suggestion: str, fallback: str) -> str:
        for n in graph.nodes:
            if n.name == suggestion or n.model_id == suggestion:
                return n.model_id
        # Treat suggestion as a raw directory id (candidate not present as a node).
        return suggestion or fallback

    out = Graph()
    for n in graph.nodes:
        if n.name in prior_names:
            out.add(n.name, model_for(suggestion, n.model_id))
        else:
            out.add(n.name, n.model_id)
    for e in graph.edges:
        out.edges.append(Edge(frm=e.frm, to=e.to, kind=e.kind))
    return out
