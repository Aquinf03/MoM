"""CLI for the MoM SDK: inspect catalog, plan graphs, run, chat, serve."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, TextIO

import mom
from mom.app import MoM
from mom.config import Settings
from mom.errors import MomError
from mom.graph import Graph
from mom.logging_config import setup_logging
from mom.scheduler import RunResult, plan_graph


def main(argv: list[str] | None = None, *, app: MoM | None = None) -> int:
    parser = _parser()
    raw = list(argv if argv is not None else sys.argv[1:])
    args = parser.parse_args(_front_globals(raw))
    if not args.cmd:
        parser.print_help()
        return 0
    try:
        return int(args.func(args, app=app))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except (MomError, KeyError, ValueError, OSError) as e:
        _fail(str(e), json_mode=getattr(args, "json", False))
        return 1


def console() -> None:
    raise SystemExit(main())


def ping_main(argv: list[str] | None = None) -> None:
    raise SystemExit(main(["version", *(argv if argv is not None else sys.argv[1:])]))


def serve_main(argv: list[str] | None = None) -> None:
    raise SystemExit(main(["serve", *(argv if argv is not None else sys.argv[1:])]))


_GLOBAL_FLAGS = frozenset({"--json", "-v", "--verbose"})


def _front_globals(argv: list[str]) -> list[str]:
    """Allow `mom --json models` as well as `mom models --json`."""
    flags: list[str] = []
    i = 0
    while i < len(argv) and argv[i] in _GLOBAL_FLAGS:
        flags.append(argv[i])
        i += 1
    rest = argv[i:]
    if not rest or rest[0] in {"-h", "--help"}:
        return argv
    return [rest[0], *flags, *rest[1:]]


def _parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--json", action="store_true", help="machine-readable output")
    shared.add_argument("-v", "--verbose", action="store_true", help="INFO logs (default: warnings)")

    p = argparse.ArgumentParser(
        prog="mom",
        description="MoM SDK command line: directory, graphs, run, chat, serve.",
    )
    sub = p.add_subparsers(dest="cmd")

    v = sub.add_parser("version", parents=[shared], help="package + native ping (alias: mom-ping)")
    v.set_defaults(func=_cmd_version)

    d = sub.add_parser("doctor", parents=[shared], help="health, readiness, env")
    d.add_argument("--no-probe", action="store_true", help="skip weight / upstream probes")
    d.set_defaults(func=_cmd_doctor)

    m = sub.add_parser("models", parents=[shared], help="list directory ids")
    m.set_defaults(func=_cmd_models)

    g = sub.add_parser("graphs", parents=[shared], help="list named graphs")
    g.set_defaults(func=_cmd_graphs)

    pl = sub.add_parser("plan", parents=[shared], help="dump execution plan for a named graph")
    pl.add_argument("name", nargs="?", help="graph name (default: MOM_DEFAULT_GRAPH)")
    pl.set_defaults(func=_cmd_plan)

    r = sub.add_parser("run", parents=[shared], help="one-shot run_named / Graph.from_dict")
    r.add_argument("prompt", help="input text, or JSON if --input-json")
    r.add_argument("--graph", help="named graph (default: MOM_DEFAULT_GRAPH)")
    r.add_argument("--graph-json", type=Path, help="Graph.to_dict() JSON file")
    r.add_argument("--input-json", action="store_true", help="parse prompt as JSON")
    r.add_argument("-q", "--quiet", action="store_true", help="text only, no metrics line")
    r.set_defaults(func=_cmd_run)

    c = sub.add_parser("chat", parents=[shared], help="multi-turn Session (REPL if no message)")
    c.add_argument("message", nargs="?", help="one turn; omit for REPL")
    c.add_argument("--graph", help="named graph")
    c.add_argument("-q", "--quiet", action="store_true")
    c.set_defaults(func=_cmd_chat)

    s = sub.add_parser("serve", parents=[shared], help="HTTP API (alias: mom-serve)")
    s.add_argument("--host", help="bind host (default: MOM_HOST)")
    s.add_argument("--port", type=int, help="bind port (default: MOM_PORT)")
    s.set_defaults(func=_cmd_serve)
    return p


def _cmd_version(args: argparse.Namespace, *, app: MoM | None = None) -> int:
    payload = {
        "version": mom.__version__,
        "native": bool(mom.NATIVE),
        "core_version": mom.core_version(),
        "ping": mom.ping(),
    }
    if args.json:
        _print_json(payload)
    else:
        print(f"mom {payload['version']} native={payload['native']} ping={payload['ping']!r}")
    return 0


def _cmd_doctor(args: argparse.Namespace, *, app: MoM | None = None) -> int:
    handle = _app(args, app)
    body = handle.ready(probe=not args.no_probe)
    if args.json:
        _print_json(body)
    else:
        print(f"status     {body.get('status')}")
        print(f"ready      {body.get('ready')}")
        print(f"version    {body.get('version')}  native={body.get('native')}")
        print(f"backend    {body.get('backend')}  default_graph={body.get('default_graph')}")
        print(f"weights    {body.get('weights_dir')}")
        print(f"models     {body.get('models')}  {', '.join(body.get('model_ids') or [])}")
        up = body.get("upstream") or {}
        if up.get("weights"):
            for name, check in up["weights"].items():
                print(f"source     {name}: {check}")
        elif up:
            print(f"upstream   {up}")
    ready = bool(body.get("ready"))
    ok = body.get("status") in {"ok"} and ready
    return 0 if ok else 1


def _cmd_models(args: argparse.Namespace, *, app: MoM | None = None) -> int:
    handle = _app(args, app)
    rows = []
    for mid in handle.directory.ids():
        entry = handle.directory.get(mid)
        rows.append(
            {
                "id": mid,
                "tags": sorted(entry.tags),
                "modality": entry.meta.get("modality"),
                "meta": {k: v for k, v in entry.meta.items() if k != "modality"},
            }
        )
    if args.json:
        _print_json({"models": rows})
        return 0
    if not rows:
        print("no models registered")
        return 0
    width = max(len(r["id"]) for r in rows)
    for r in rows:
        tags = ",".join(r["tags"]) or "-"
        mod = r["modality"] or "-"
        print(f"{r['id']:<{width}}  {mod:<10} {tags}")
    return 0


def _cmd_graphs(args: argparse.Namespace, *, app: MoM | None = None) -> int:
    handle = _app(args, app)
    rows = []
    for spec in handle.registry.specs():
        missing = sorted(mid for mid in spec.requires if mid not in handle.directory)
        rows.append(
            {
                "name": spec.name,
                "runnable": not missing,
                "missing": missing,
                "shape": spec.shape,
                "latency_hideable": spec.latency_hideable,
                "description": spec.description,
                "requires": sorted(spec.requires),
            }
        )
    if args.json:
        _print_json({"graphs": rows, "default": handle.default_graph_name})
        return 0
    if not rows:
        print("no graphs registered")
        return 0
    width = max(len(r["name"]) for r in rows)
    for r in rows:
        flag = "ok" if r["runnable"] else "missing"
        hide = "hide" if r["latency_hideable"] else "serial"
        extra = f"  missing={','.join(r['missing'])}" if r["missing"] else ""
        print(
            f"{r['name']:<{width}}  {flag:<7} {hide:<6} {r['shape']:<16} {r['description']}{extra}"
        )
    return 0


def _cmd_plan(args: argparse.Namespace, *, app: MoM | None = None) -> int:
    handle = _app(args, app)
    name = args.name or handle.default_graph_name
    spec = handle.registry.get(name)
    plan = plan_graph(spec.graph)
    payload = {"graph": name, "plan": plan, "graph_dict": spec.graph.to_dict()}
    if args.json:
        _print_json(payload)
    else:
        print(f"graph {name}  shape={spec.shape}")
        for i, step in enumerate(plan.get("steps") or [], start=1):
            kind = step.get("type", "?")
            if kind == "speculate":
                print(f"  {i}. speculate  router={step.get('router')}  prior={step.get('prior')}")
            else:
                print(f"  {i}. run        node={step.get('node')}")
    return 0


def _cmd_run(args: argparse.Namespace, *, app: MoM | None = None) -> int:
    handle = _app(args, app)
    prompt: Any = json.loads(args.prompt) if args.input_json else args.prompt
    graph: str | Graph | None
    if args.graph_json is not None:
        graph = _graph_from_file(args.graph_json)
    else:
        graph = args.graph
    result = handle.run(prompt, graph=graph)
    return _emit_result(result, json_mode=args.json, quiet=args.quiet)


def _cmd_chat(args: argparse.Namespace, *, app: MoM | None = None) -> int:
    handle = _app(args, app)
    if args.message is not None:
        reply = handle.chat(args.message, graph=args.graph)
        raw = reply.raw or RunResult(output=reply.output, metrics=reply.metrics)
        return _emit_result(raw, json_mode=args.json, quiet=args.quiet)
    if args.json:
        _fail("chat REPL is text-only; pass a message with --json", json_mode=True)
        return 2
    return _repl(handle, graph=args.graph, quiet=args.quiet)


def _cmd_serve(args: argparse.Namespace, *, app: MoM | None = None) -> int:
    from mom.server import main as serve

    settings = Settings.from_env()
    if args.host:
        settings = replace(settings, host=args.host)
    if args.port is not None:
        settings = replace(settings, port=args.port)
    serve(settings)
    return 0


def _repl(handle: MoM, *, graph: str | None, quiet: bool) -> int:
    print("mom chat  /quit to exit", file=sys.stderr)
    handle.session(graph=graph, fresh=True)
    while True:
        try:
            line = input("mom> ")
        except EOFError:
            print()
            return 0
        text = line.strip()
        if not text:
            continue
        if text in {"/quit", "/exit", "/q"}:
            return 0
        reply = handle.chat(text, graph=graph)
        print(reply.text)
        if not quiet:
            _metrics_line(reply.metrics, reply.model, file=sys.stderr)
    return 0


def _app(args: argparse.Namespace, injected: MoM | None) -> MoM:
    if injected is not None:
        return injected
    settings = Settings.from_env()
    if not args.verbose:
        settings = replace(settings, log_level="WARNING")
    setup_logging(level=settings.log_level, json_logs=settings.log_json, stream=sys.stderr)
    return MoM(settings)


def _graph_from_file(path: Path) -> Graph:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    if "nodes" in data:
        return Graph.from_dict(data)
    if isinstance(data.get("graph"), dict):
        return Graph.from_dict(data["graph"])
    raise ValueError(f"{path} needs Graph.to_dict() or a nested 'graph' key")


def _emit_result(result: RunResult, *, json_mode: bool, quiet: bool) -> int:
    text, model = _text_model(result.output)
    if json_mode:
        _print_json({"output": result.output, "text": text, "model": model, "metrics": result.metrics})
        return 0
    print(text)
    if not quiet:
        _metrics_line(result.metrics, model, file=sys.stderr)
    return 0


def _metrics_line(metrics: dict[str, Any], model: str | None, *, file: TextIO) -> None:
    total = metrics.get("total_ms")
    orch = metrics.get("orchestration_overhead_ms")
    spec = metrics.get("spec")
    bits = []
    if model:
        bits.append(f"model={model}")
    if total is not None:
        bits.append(f"total_ms={float(total):.1f}")
    if orch is not None:
        bits.append(f"orch_ms={float(orch):.1f}")
    if spec is not None:
        bits.append(f"spec={spec}")
    if bits:
        print(" ".join(bits), file=file)


def _text_model(output: Any) -> tuple[str, str | None]:
    if isinstance(output, dict):
        text = output.get("text")
        model = output.get("model")
        if isinstance(text, str):
            return text, model if isinstance(model, str) else None
        return str(output), model if isinstance(model, str) else None
    return str(output), None


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, default=str, indent=2))


def _fail(msg: str, *, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps({"error": msg}), file=sys.stderr)
    else:
        print(msg, file=sys.stderr)


if __name__ == "__main__":
    console()
