"""In-process chat over Hugging Face / path weights."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from mom.cancel import CancelToken
from mom.config import Settings
from mom.engines import get_causal
from mom.state import StateStore
from mom.turn import get_messages
from mom.util_text import as_text_light
from mom.weights import resolve_source


class _CausalLike(Protocol):
    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        max_new_tokens: int | None = None,
        cancel: Any = None,
    ) -> str: ...


class LocalChatModel:
    """
    Causal LM loaded from a Hub id or filesystem path.

    Engines are process-cached by resolved path so many MoM nodes can
    share one set of weights.
    """

    def __init__(
        self,
        source: str,
        *,
        settings: Settings | None = None,
        model_id: str = "local.chat",
        system: str | None = None,
        engine: _CausalLike | None = None,
        max_new_tokens: int | None = None,
    ) -> None:
        self.source = source
        self.settings = settings or Settings.from_env()
        self.model_id = model_id
        self.system = system
        self._engine = engine
        self._path: Path | None = None
        self._max_new_tokens = max_new_tokens

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

    def _get_engine(self) -> _CausalLike:
        if self._engine is not None:
            return self._engine
        s = self.settings
        self._engine = get_causal(
            self._resolve(),
            device=s.device,
            dtype=s.dtype,
            max_new_tokens=self._max_new_tokens or s.max_new_tokens,
        )
        return self._engine

    def run(
        self,
        input: Any,
        state: StateStore,
        cancel: CancelToken | None = None,
    ) -> Any:
        if cancel is not None:
            cancel.check()
        messages = _build_messages(input, state, system=self.system)
        text = self._get_engine().generate(
            messages,
            max_new_tokens=self._max_new_tokens or self.settings.max_new_tokens,
            cancel=cancel,
        )
        weights = str(self._path) if self._path is not None else self.source
        state.set("last_model", self.model_id)
        state.set("weights_path", weights)
        return {
            "text": text,
            "model": self.model_id,
            "source": self.source,
            "weights": weights,
            "backend": "local",
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
    text = as_text_light(input)
    if not msgs or msgs[-1].get("content") != text:
        msgs.append({"role": "user", "content": text})
    return msgs
