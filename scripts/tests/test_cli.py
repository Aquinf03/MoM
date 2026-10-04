"""CLI covers inspect + run against an injected MoM (no Hub weights)."""

from __future__ import annotations

import json
from pathlib import Path

from mom import Graph, GraphRegistry, ModelDirectory, MoM
from mom.cli import main


class Echo:
    def run(self, input, state, cancel=None):
        return {"text": str(input), "model": "echo"}


def _app() -> MoM:
    d = ModelDirectory()
    d.register("echo", Echo, tags={"generator"}, modality="text")
    app = MoM(load_production=False, directory=d, registry=GraphRegistry(), graph="echo")
    app.add_graph(
        "echo",
        Graph().add("g", "echo"),
        requires={"echo"},
        description="single echo",
        latency_hideable=True,
        shape="single",
    )
    return app


def test_help_and_version(capsys):
    assert main([]) == 0
    help_out = capsys.readouterr().out
    assert "doctor" in help_out
    assert main(["version"]) == 0
    ver = capsys.readouterr().out
    assert "mom " in ver
    assert main(["version", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "version" in payload
    assert "native" in payload


def test_models_graphs_plan(capsys):
    app = _app()
    assert main(["--json", "models"], app=app) == 0
    models = json.loads(capsys.readouterr().out)
    assert models["models"][0]["id"] == "echo"

    assert main(["--json", "graphs"], app=app) == 0
    graphs = json.loads(capsys.readouterr().out)
    echo = next(g for g in graphs["graphs"] if g["name"] == "echo")
    assert echo["runnable"] is True

    assert main(["--json", "plan", "echo"], app=app) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["plan"]["steps"][0]["type"] == "run"


def test_run_and_chat(capsys):
    app = _app()
    assert main(["run", "hello", "--graph", "echo", "--json"], app=app) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["text"] == "hello"
    assert body["model"] == "echo"
    assert "total_ms" in body["metrics"]

    assert main(["--json", "chat", "hi", "--graph", "echo"], app=app) == 0
    chat = json.loads(capsys.readouterr().out)
    assert chat["text"] == "hi"


def test_run_graph_json(tmp_path: Path, capsys):
    path = tmp_path / "g.json"
    path.write_text(json.dumps(Graph().add("g", "echo").to_dict()), encoding="utf-8")
    assert main(["--json", "run", "z", "--graph-json", str(path)], app=_app()) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["text"] == "z"


def test_unknown_graph_fails(capsys):
    assert main(["run", "x", "--graph", "nope"], app=_app()) == 1
    err = capsys.readouterr().err
    assert "unknown graph" in err or "nope" in err


def test_doctor_no_probe(capsys):
    code = main(["--json", "doctor", "--no-probe"], app=_app())
    body = json.loads(capsys.readouterr().out)
    assert "status" in body
    assert "ready" in body
    assert code in (0, 1)
