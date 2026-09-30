"""In-process embeddings over Hugging Face / path weights."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from mom.cancel import CancelToken
from mom.config import Settings
from mom.engines import get_embed
from mom.state import StateStore
from mom.util_text import as_text_light
from mom.weights import resolve_source


class _EmbedLike(Protocol):
    def embed(self, text: str, *, cancel: Any = None) -> list[float]: ...


class LocalEmbedModel:
    def __init__(
        self,
        source: str,
        *,
        settings: Settings | None = None,
        model_id: str = "local.embed",
        engine: _EmbedLike | None = None,
    ) -> None:
        self.source = source
        self.settings = settings or Settings.from_env()
        self.model_id = model_id
        self._engine = engine
        self._path: Path | None = None

    def _resolve(self) -> Path:
        if self._path is None:
            self._path = resolve_source(
                self.source,
                self.settings.weights_dir,
                token=self.settings.hf_token,
                revision=self.settings.hf_revision,
            )
        return self._path

    @property
    def path(self) -> Path | None:
        if self._path is not None:
            return self._path
        if self._engine is not None:
            return None
        return self._resolve()

    def _get_engine(self) -> _EmbedLike:
        if self._engine is not None:
            return self._engine
        s = self.settings
        self._engine = get_embed(self._resolve(), device=s.device, dtype=s.dtype)
        return self._engine

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        if cancel is not None:
            cancel.check()
        text = as_text_light(input)
        vec = self._get_engine().embed(text, cancel=cancel)
        weights = str(self._path) if self._path is not None else self.source
        state.set("last_embed_model", self.model_id)
        return {
            "embedding": vec,
            "dims": len(vec),
            "model": self.model_id,
            "source": self.source,
            "weights": weights,
            "backend": "local",
        }
