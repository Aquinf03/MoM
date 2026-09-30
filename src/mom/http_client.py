"""Shared HTTP client for production adapters (timeouts + limited retries)."""

from __future__ import annotations

from typing import Any

import httpx

from mom.config import Settings
from mom.errors import AdapterAuthError, AdapterError, AdapterTimeout


def build_client(settings: Settings) -> httpx.Client:
    timeout = httpx.Timeout(
        settings.http_timeout_s,
        connect=settings.http_connect_timeout_s,
    )
    return httpx.Client(timeout=timeout, follow_redirects=True)


def request_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: Any = None,
    model_id: str | None = None,
    max_retries: int = 2,
) -> Any:
    """POST/GET JSON with retries on transient errors only."""
    last_exc: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.request(method, url, headers=headers, json=json_body)
            if resp.status_code in (401, 403):
                raise AdapterAuthError(
                    f"auth failed ({resp.status_code}) for {url}",
                    model_id=model_id,
                )
            if resp.status_code in (408, 429, 500, 502, 503, 504) and attempt < max_retries:
                continue
            if resp.status_code >= 400:
                raise AdapterError(
                    f"upstream {resp.status_code}: {resp.text[:500]}",
                    model_id=model_id,
                )
            return resp.json()
        except httpx.TimeoutException as e:
            last_exc = e
            if attempt >= max_retries:
                raise AdapterTimeout(f"timeout calling {url}", model_id=model_id, cause=e) from e
        except httpx.TransportError as e:
            last_exc = e
            if attempt >= max_retries:
                raise AdapterError(f"transport error calling {url}: {e}", model_id=model_id, cause=e) from e
    raise AdapterError(f"request failed for {url}", model_id=model_id, cause=last_exc)
