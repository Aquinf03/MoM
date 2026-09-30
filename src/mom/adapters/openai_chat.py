"""OpenAI-compatible chat completions (OpenAI, Azure, Ollama, vLLM, …)."""

from __future__ import annotations

from typing import Any

from mom.cancel import CancelToken
from mom.config import Settings
from mom.errors import AdapterError
from mom.http_client import build_client, request_json
from mom.state import StateStore
from mom.turn import get_messages
from mom.util_text import as_text_light


class OpenAIChatModel:
    """
    Chat via `/v1/chat/completions`.

    Works with OpenAI cloud and any OpenAI-compatible local server.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        settings: Settings | None = None,
        model_id: str = "openai.chat",
        system: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.settings = settings or Settings.from_env()
        self.model_id = model_id
        self.system = system

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        if cancel is not None:
            cancel.check()
        messages = _build_messages(input, state, system=self.system)
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
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
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise AdapterError(
                f"unexpected chat response shape: {data!r}"[:400],
                model_id=self.model_id,
                cause=e,
            ) from e
        if cancel is not None:
            cancel.check()
        usage = data.get("usage") or {}
        state.set("last_model", self.model_id)
        return {
            "text": text,
            "model": self.model_id,
            "provider_model": self.model,
            "usage": usage,
        }


def _build_messages(input: Any, state: StateStore, *, system: str | None) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = []
    if system:
        msgs.append({"role": "system", "content": system})
    history = get_messages(state)
    if history:
        for m in history[-12:]:
            role = m.get("role")
            content = m.get("content")
            if role in ("user", "assistant", "system") and isinstance(content, str):
                msgs.append({"role": role, "content": content})
    # Current hop input (Session already added user turn; avoid duplicate if last matches)
    text = as_text_light(input)
    if not msgs or msgs[-1].get("content") != text:
        msgs.append({"role": "user", "content": text})
    return msgs
