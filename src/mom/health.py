"""Health / readiness for colocated deployments."""

from __future__ import annotations

from typing import Any

import mom
from mom.config import Settings
from mom.directory import ModelDirectory


def health_check(
    directory: ModelDirectory | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """
    Process health. `status` is `ok` | `degraded`.

    Does not call upstream models (use `readiness_check` for that).
    """
    settings = settings or Settings.from_env()
    native_ok = bool(mom.NATIVE)
    ping = mom.ping()
    ids = directory.ids() if directory is not None else []
    status = "ok" if native_ok else "degraded"
    return {
        "status": status,
        "version": mom.__version__,
        "native": native_ok,
        "ping": ping,
        "models": len(ids),
        "model_ids": ids,
        "prefer_local": settings.prefer_local,
        "default_graph": settings.default_graph,
    }


def readiness_check(
    directory: ModelDirectory,
    settings: Settings | None = None,
    *,
    probe_local: bool = True,
) -> dict[str, Any]:
    """
    Readiness: directory non-empty; optionally probe local OpenAI-compatible /v1/models.
    """
    import httpx

    settings = settings or Settings.from_env()
    base = health_check(directory, settings)
    ready = len(directory) > 0 and mom.NATIVE
    upstream: dict[str, Any] = {"probed": False}
    if probe_local and settings.prefer_local:
        upstream["probed"] = True
        url = settings.local_openai_base_url.rstrip("/") + "/models"
        try:
            with httpx.Client(timeout=httpx.Timeout(3.0, connect=1.0)) as client:
                r = client.get(
                    url,
                    headers={"Authorization": f"Bearer {settings.local_openai_api_key}"},
                )
                upstream["status_code"] = r.status_code
                upstream["ok"] = r.status_code < 500
                if r.status_code >= 500:
                    ready = False
        except Exception as e:  # noqa: BLE001 — surface as not-ready
            upstream["ok"] = False
            upstream["error"] = str(e)
            ready = False
    base["ready"] = ready
    base["upstream"] = upstream
    base["status"] = "ok" if ready else "not_ready"
    return base
