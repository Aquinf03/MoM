"""Anthropic Messages API chat adapter."""

from __future__ import annotations

from typing import Any

from mom.cancel import CancelToken
from mom.config import Settings
from mom.errors import AdapterAuthError, AdapterError
from mom.http_client import build_client, request_json
from mom.state import StateStore
from mom.turn import get_messages
from mom.util_text import as_text_light


class AnthropicChatModel:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        base_url: str = "https://api.anthropic.com",
        version: str = "2023-06-01",
        settings: Settings | None = None,
        model_id: str = "anthropic.chat",
        system: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.version = version
        self.settings = settings or Settings.from_env()
        self.model_id = model_id
        self.system = system

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        if not self.api_key:
            raise AdapterAuthError("ANTHROPIC_API_KEY is not set", model_id=self.model_id)
        if cancel is not None:
            cancel.check()
        messages = []
        for m in get_messages(state)[-12:]:
            role = m.get("role")
            content = m.get("content")
            if role in ("user", "assistant") and isinstance(content, str):
                messages.append({"role": role, "content": content})
        text = as_text_light(input)
        if not messages or messages[-1].get("content") != text:
            messages.append({"role": "user", "content": text})
        if not messages:
            messages = [{"role": "user", "content": text}]

        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.version,
            "content-type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": messages,
        }
        if self.system:
            body["system"] = self.system
        with build_client(self.settings) as client:
            data = request_json(
                client,
                "POST",
                url,
                headers=headers,
                json_body=body,
                model_id=self.model_id,
                max_retries=self.settings.http_max_retries,
            )
        try:
            blocks = data["content"]
            text_out = "".join(
                b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
            )
        except (KeyError, TypeError) as e:
            raise AdapterError(
                f"unexpected anthropic response: {data!r}"[:400],
                model_id=self.model_id,
                cause=e,
            ) from e
        state.set("last_model", self.model_id)
        return {
            "text": text_out,
            "model": self.model_id,
            "provider_model": self.model,
            "usage": data.get("usage") or {},
        }
