"""SDK surface stability — installed package imports + graph wire format."""

from __future__ import annotations

import mom
from mom import Graph, ModelDirectory, run
from mom.adapter import Model
from mom.api import STABLE_API


def test_version_and_ping():
    assert mom.__version__
    assert isinstance(mom.ping(), str)
    assert isinstance(mom.NATIVE, bool)


def test_stable_api_names_exportable():
    for name in STABLE_API:
        assert hasattr(mom, name) or name in {"Edge", "Node", "Model"}
        if name == "Model":
            assert Model is not None
        elif name in {"Edge", "Node"}:
            assert hasattr(mom, name)


def test_model_protocol_structural():
    class X:
        def run(self, input, state, cancel=None):
            return input

    assert isinstance(X(), Model)


def test_graph_roundtrip_and_validation():
    g = Graph().add("a", "fast").add("b", "slow").link("a", "b")
    g2 = Graph.from_dict(g.to_dict())
    assert g2.to_dict() == g.to_dict()
    assert g.copy().to_dict() == g.to_dict()

    try:
        Graph().add("a", "x").link("a", "missing")
        assert False, "expected KeyError"
    except KeyError:
        pass

    try:
        Graph().add("a", "x").add("a", "y")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_sdk_consumer_register_and_run(directory, store):
    g = Graph().add("g", "fast")
    r = run(g, "hello-sdk", directory, state=store)
    assert r.output["model"] == "fast"
    assert r.output["text"] == "hello-sdk"
    assert r.metrics["total_ms"] >= 0
