"""OpenAI-compatible embeddings."""

from __future__ import annotations

from typing import Any

from mom.cancel import CancelToken
from mom.config import Settings
from mom.errors import AdapterError
from mom.http_client import build_client, request_json
from mom.state import StateStore
from mom.util_text import as_text_light


class OpenAIEmbedModel:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        settings: Settings | None = None,
        model_id: str = "openai.embed",
        raw: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.settings = settings or Settings.from_env()
        self.model_id = model_id
        self.raw = raw

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        if cancel is not None:
            cancel.check()
        text = as_text_light(input)
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with build_client(self.settings) as client:
            data = request_json(
                client,
                "POST",
                url,
                headers=headers,
                json_body={"model": self.model, "input": text},
                model_id=self.model_id,
                max_retries=self.settings.http_max_retries,
            )
        try:
            vec = data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as e:
            raise AdapterError(
                f"unexpected embedding response: {data!r}"[:400],
                model_id=self.model_id,
                cause=e,
            ) from e
        state.set("embedding", vec)
        if self.raw:
            return vec
        return {"embedding": vec, "dims": len(vec), "model": self.model_id}
