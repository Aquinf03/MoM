"""Health / readiness for colocated deployments."""

from __future__ import annotations

from typing import Any

import mom
from mom.config import Settings
from mom.directory import ModelDirectory
from mom.weights import looks_like_hf_id, looks_like_path, resolve_source


def health_check(
    directory: ModelDirectory | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """
    Process health. `status` is `ok` | `degraded`.

    Does not call models (use `readiness_check` for that).
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
        "backend": settings.backend,
        "weights_dir": str(settings.weights_dir),
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
    Readiness: directory non-empty; for local backend, check weight sources;
    for http backend, optionally probe OpenAI-compatible /v1/models.
    """
    settings = settings or Settings.from_env()
    base = health_check(directory, settings)
    ready = len(directory) > 0 and mom.NATIVE
    upstream: dict[str, Any] = {"probed": False, "backend": settings.backend}

    if not probe_local:
        base["ready"] = ready
        base["upstream"] = upstream
        base["status"] = "ok" if ready else "not_ready"
        return base

    if settings.backend == "local":
        upstream["probed"] = True
        sources = {
            "fast": settings.chat_fast_source,
            "strong": settings.chat_strong_source,
            "embed": settings.embed_source,
        }
        checks: dict[str, Any] = {}
        ok = True
        for name, src in sources.items():
            try:
                if looks_like_path(src):
                    path = resolve_source(
                        src,
                        settings.weights_dir,
                        token=settings.hf_token,
                        revision=settings.hf_revision,
                        download=False,
                    )
                    checks[name] = {"ok": True, "path": str(path)}
                elif looks_like_hf_id(src):
                    # Hub id is valid config; download happens on first use
                    checks[name] = {"ok": True, "source": src, "cached": False}
                    try:
                        path = resolve_source(
                            src,
                            settings.weights_dir,
                            token=settings.hf_token,
                            revision=settings.hf_revision,
                            download=False,
                        )
                        checks[name] = {"ok": True, "source": src, "cached": True, "path": str(path)}
                    except Exception:  # noqa: BLE001
                        pass
                else:
                    checks[name] = {"ok": False, "error": f"invalid source {src!r}"}
                    ok = False
            except Exception as e:  # noqa: BLE001
                checks[name] = {"ok": False, "error": str(e)}
                ok = False
        upstream["weights"] = checks
        upstream["ok"] = ok
        if not ok:
            ready = False
    else:
        import httpx

        upstream["probed"] = True
        url = settings.local_openai_base_url.rstrip("/") + "/models"
        if not settings.prefer_local:
            url = settings.openai_base_url.rstrip("/") + "/models"
        try:
            key = (
                settings.local_openai_api_key
                if settings.prefer_local
                else (settings.openai_api_key or "")
            )
            with httpx.Client(timeout=httpx.Timeout(3.0, connect=1.0)) as client:
                r = client.get(url, headers={"Authorization": f"Bearer {key}"})
                upstream["status_code"] = r.status_code
                upstream["ok"] = r.status_code < 500
                if r.status_code >= 500:
                    ready = False
        except Exception as e:  # noqa: BLE001
            upstream["ok"] = False
            upstream["error"] = str(e)
            ready = False

    base["ready"] = ready
    base["upstream"] = upstream
    base["status"] = "ok" if ready else "not_ready"
    return base
