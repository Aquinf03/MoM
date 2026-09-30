"""
Starter product built on MoM.

This is what "use MoM to build full-fledged crap" means:
- one MoM() handle
- your own tools registered into the directory
- your own graph wired from directory ids
- chat + HTTP API for a real assistant

Run:

  pip install -r requirements-local.txt
  cp -n .env.example .env   # MOM_CHAT_FAST = Hub id or path
  python -m apps.assistant            # REPL
  python -m apps.assistant serve      # HTTP on MOM_PORT
  python -m apps.assistant once "hi"
  # or: PYTHONPATH=scripts/helpers:src python -m apps.assistant once "hi"
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Repo layout: allow `python -m apps.assistant` from root via helpers on path
ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "scripts" / "helpers")]

from mom import Graph, MoM, StateStore
from mom.cancel import CancelToken


class TicketTool:
    """Example product tool — pretend CRM / billing lookup."""

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        if cancel is not None:
            cancel.check()
        q = input if isinstance(input, str) else str(input)
        if isinstance(input, dict):
            q = str(input.get("text") or input.get("query") or q)
        ticket = {
            "id": "T-1042",
            "status": "open",
            "customer": "acme",
            "summary": f"matched query: {q[:80]}",
            "balance_due": 42.0,
        }
        state.set("ticket", ticket)
        return {
            "text": (
                f"Ticket {ticket['id']} ({ticket['status']}) for {ticket['customer']}: "
                f"{ticket['summary']}. Balance due ${ticket['balance_due']:.2f}."
            ),
            "model": "app.ticket",
            "ticket": ticket,
        }


def build_product() -> MoM:
    """Assemble the assistant product on top of MoM."""
    app = MoM()  # local HF / path adapters from env

    # Your stuff — not stubs
    app.register("app.ticket", TicketTool, tags={"tool", "product"}, modality="tool")

    # Product graph: always fetch ticket context, then speculate chat
    # (simple depend → speculate composition = full app topology)
    support = (
        Graph()
        .add("ticket", "app.ticket")
        .add("router", "prod.router")
        .add("gen", "prod.chat.fast")
        .link("ticket", "router")
        .speculate("router", "gen")
    )
    app.add_graph(
        "support",
        support,
        shape="pipeline+speculate",
        requires={"app.ticket", "prod.router", "prod.chat.fast", "prod.chat.strong"},
        latency_hideable=True,
        description="ticket tool → speculate chat",
        tags={"product", "support"},
    )
    app.default_graph_name = "support"
    return app


def repl(app: MoM) -> None:
    print("MoM assistant (graph=support). Empty line to quit.")
    print(f"health: {app.health()['status']} models={app.health()['models']}")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            break
        reply = app.chat(line, graph="support")
        print(f"bot> {reply.text}")
        print(f"     model={reply.model}  {reply.total_ms:.0f}ms  spec={reply.metrics.get('spec')}")


def main(argv: list[str] | None = None) -> None:
    argv = list(argv if argv is not None else sys.argv[1:])
    app = build_product()
    if not argv or argv[0] == "repl":
        repl(app)
        return
    if argv[0] == "serve":
        _serve(app)
        return
    if argv[0] == "once":
        msg = " ".join(argv[1:]) or "What's the status of my ticket?"
        try:
            reply = app.chat(msg, graph="support")
        except Exception as e:  # noqa: BLE001
            from mom.errors import AdapterError, AdapterTimeout, ConfigError

            if isinstance(e, (AdapterError, AdapterTimeout, ConfigError, OSError, ConnectionError)):
                print(
                    "Local model unavailable. Install engines and point at Hub id or path:\n"
                    "  pip install -r requirements-local.txt\n"
                    "  cp -n .env.example .env\n"
                    "  # MOM_CHAT_FAST=HuggingFaceTB/SmolLM2-135M-Instruct\n"
                    "  # or MOM_CHAT_FAST=./weights/my-model\n"
                    f"Detail: {e}",
                    file=sys.stderr,
                )
                raise SystemExit(1) from e
            raise
        print(reply.text)
        return
    print(__doc__)
    raise SystemExit(2)


def _serve(app: MoM) -> None:
    import uvicorn
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    settings = app.settings

    async def health(_: Request) -> JSONResponse:
        return JSONResponse(app.health())

    async def ready(_: Request) -> JSONResponse:
        body = app.ready()
        return JSONResponse(body, status_code=200 if body.get("ready") else 503)

    async def v1_chat(request: Request) -> JSONResponse:
        payload = await request.json()
        message = payload.get("message") or payload.get("text")
        if not message:
            return JSONResponse({"error": "missing message"}, status_code=400)
        graph = payload.get("graph") or "support"
        reply = app.chat(str(message), graph=graph)
        return JSONResponse(
            {
                "text": reply.text,
                "model": reply.model,
                "output": reply.output,
                "metrics": reply.metrics,
                "messages": app.session(graph=graph).messages,
            }
        )

    async def v1_run(request: Request) -> JSONResponse:
        payload = await request.json()
        text = payload.get("input") or payload.get("text")
        graph = payload.get("graph") or "support"
        result = app.run(text, graph=graph)
        return JSONResponse(
            {"output": result.output, "metrics": result.metrics, "graph": graph}
        )

    starlette_app = Starlette(
        routes=[
            Route("/health", health),
            Route("/ready", ready),
            Route("/v1/chat", v1_chat, methods=["POST"]),
            Route("/v1/run", v1_run, methods=["POST"]),
        ]
    )
    uvicorn.run(starlette_app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
