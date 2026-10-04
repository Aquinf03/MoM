"""BLIP caption hop — real image → text, then chat can run on the caption."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mom.cancel import CancelToken
from mom.config import Settings
from mom.engines import get_caption
from mom.image import open_image, stash_vision
from mom.state import StateStore
from mom.weights import resolve_source


class LocalCaptionModel:
    def __init__(
        self,
        source: str,
        *,
        settings: Settings | None = None,
        model_id: str = "prod.vision.caption",
        engine: Any = None,
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

    def _get_engine(self):
        if self._engine is None:
            s = self.settings
            self._engine = get_caption(self._resolve(), device=s.device, dtype=s.dtype)
        return self._engine

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        if cancel is not None:
            cancel.check()
        path, question = stash_vision(input, state)
        caption = self._get_engine().caption(open_image(path), cancel=cancel)
        state.set("caption", caption)
        state.set("last_model", self.model_id)
        text = caption if not question else f"Image: {caption}\nQuestion: {question}"
        return {
            "text": text,
            "caption": caption,
            "question": question,
            "image": str(path),
            "model": self.model_id,
            "backend": "local",
        }
