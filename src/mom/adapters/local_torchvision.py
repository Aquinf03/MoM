"""torchvision ImageNet classifier hop — real pixels, real ResNet weights."""

from __future__ import annotations

from typing import Any

from mom.cancel import CancelToken
from mom.config import Settings
from mom.engines import get_torchvision
from mom.image import open_image, stash_vision
from mom.state import StateStore


class LocalTorchVisionModel:
    def __init__(
        self,
        name: str = "resnet18",
        *,
        settings: Settings | None = None,
        model_id: str = "prod.vision.torch",
        engine: Any = None,
        top_k: int = 5,
    ) -> None:
        self.name = name
        self.settings = settings or Settings.from_env()
        self.model_id = model_id
        self.top_k = top_k
        self._engine = engine

    def _get_engine(self):
        if self._engine is None:
            s = self.settings
            self._engine = get_torchvision(self.name, device=s.device, dtype=s.dtype)
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
        ranked = self._get_engine().classify(open_image(path), cancel=cancel, top_k=self.top_k)
        labels = ", ".join(f"{name} ({score:.2f})" for name, score in ranked)
        top = ranked[0][0] if ranked else ""
        state.set("vision_labels", labels)
        state.set("vision_top", top)
        state.set("last_model", self.model_id)
        desc = f"torchvision {self.name} top: {labels}"
        text = desc if not question else f"{desc}\nQuestion: {question}"
        return {
            "text": text,
            "labels": [{"name": n, "score": s} for n, s in ranked],
            "top": top,
            "question": question,
            "image": str(path),
            "model": self.model_id,
            "backend": "torchvision",
        }
