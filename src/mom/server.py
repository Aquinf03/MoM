"""HTTP serving surface for production deployments (Starlette)."""

from __future__ import annotations

import time
import uuid
from typing import Any

from mom.config import Settings
from mom.errors import AdapterError, ConfigError, MomError
from mom.health import health_check, readiness_check
from mom.limits import LimitExceeded, Limiter
from mom.logging_config import get_logger, setup_logging
from mom.runtime import build_directory, build_registry, concurrency_limits
from mom.scheduler import run_named
from mom.session import Session
from mom.state import StateStore

log = get_logger("mom.server")


def create_app(settings: Settings | None = None):
    """Build a Starlette app: /health /ready /v1/run /v1/chat."""
    try:
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.routing import Route
    except ImportError as e:
        raise ConfigError(
            "server extras required: pip install 'mom[server]' or pip install starlette uvicorn"
        ) from e

    settings = settings or Settings.from_env()
    setup_logging(level=settings.log_level, json_logs=settings.log_json)
    directory = build_directory(settings)
    registry = build_registry(directory)
    limiter = Limiter(concurrency_limits(settings))

    async def health(_: Request) -> JSONResponse:
        return JSONResponse(health_check(directory, settings))

    async def ready(_: Request) -> JSONResponse:
        body = readiness_check(directory, settings, probe_local=settings.prefer_local)
        code = 200 if body.get("ready") else 503
        return JSONResponse(body, status_code=code)

    async def v1_run(request: Request) -> JSONResponse:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        t0 = time.perf_counter()
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid JSON body"}, status_code=400)
        text = payload.get("input")
        if text is None:
            text = payload.get("prompt") or payload.get("text")
        if text is None:
            return JSONResponse({"error": "missing input"}, status_code=400)
        graph_name = payload.get("graph") or settings.default_graph
        state = StateStore()
        if isinstance(payload.get("state"), dict):
            for k, v in payload["state"].items():
                state.set(str(k), v)
        try:
            result = run_named(
                graph_name,
                text,
                directory,
                registry,
                state=state,
                limits=limiter,
            )
        except KeyError as e:
            return JSONResponse({"error": str(e), "request_id": request_id}, status_code=404)
        except LimitExceeded as e:
            return JSONResponse({"error": str(e), "request_id": request_id}, status_code=429)
        except AdapterError as e:
            log.exception("adapter error request_id=%s", request_id)
            return JSONResponse(
                {"error": str(e), "model_id": e.model_id, "request_id": request_id},
                status_code=502,
            )
        except MomError as e:
            return JSONResponse({"error": str(e), "request_id": request_id}, status_code=400)
        except Exception as e:  # noqa: BLE001
            log.exception("unhandled request_id=%s", request_id)
            return JSONResponse({"error": str(e), "request_id": request_id}, status_code=500)

        ms = (time.perf_counter() - t0) * 1000.0
        log.info(
            "run ok request_id=%s graph=%s total_ms=%.1f",
            request_id,
            graph_name,
            ms,
        )
        return JSONResponse(
            {
                "request_id": request_id,
                "graph": graph_name,
                "output": result.output,
                "metrics": result.metrics,
            }
        )

    async def v1_chat(request: Request) -> JSONResponse:
        """Multi-turn: client sends session-scoped messages via state or single say."""
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid JSON body"}, status_code=400)
        message = payload.get("message") or payload.get("text")
        if not isinstance(message, str) or not message.strip():
            return JSONResponse({"error": "missing message"}, status_code=400)
        graph_name = payload.get("graph") or settings.default_graph
        try:
            spec = registry.pick(directory, graph_name)
        except KeyError as e:
            return JSONResponse({"error": str(e), "request_id": request_id}, status_code=404)
        sess = Session(
            directory,
            spec.graph,
            limits=limiter,
        )
        try:
            result = sess.say(message)
        except LimitExceeded as e:
            return JSONResponse({"error": str(e), "request_id": request_id}, status_code=429)
        except AdapterError as e:
            return JSONResponse(
                {"error": str(e), "model_id": e.model_id, "request_id": request_id},
                status_code=502,
            )
        except Exception as e:  # noqa: BLE001
            log.exception("chat failed request_id=%s", request_id)
            return JSONResponse({"error": str(e), "request_id": request_id}, status_code=500)
        return JSONResponse(
            {
                "request_id": request_id,
                "graph": graph_name,
                "output": result.output,
                "messages": sess.messages,
                "metrics": result.metrics,
            }
        )

    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/ready", ready, methods=["GET"]),
        Route("/v1/run", v1_run, methods=["POST"]),
        Route("/v1/chat", v1_chat, methods=["POST"]),
    ]
    return Starlette(routes=routes)


def main(settings: Settings | None = None) -> None:
    settings = settings or Settings.from_env()
    try:
        import uvicorn
    except ImportError as e:
        raise ConfigError("pip install uvicorn starlette  (or mom[server])") from e
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
