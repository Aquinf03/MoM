"""Load a real image from hop input / shared state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mom.errors import AdapterError
from mom.state import StateStore


def question_from(input: Any, state: StateStore) -> str:
    q = state.get("question")
    if isinstance(q, str) and q.strip():
        return q
    if isinstance(input, dict):
        for k in ("text", "prompt", "question", "query"):
            v = input.get(k)
            if isinstance(v, str) and v.strip():
                return v
    if isinstance(input, str) and not _looks_like_image_path(input):
        return input
    return ""


def image_path_from(input: Any, state: StateStore) -> Path:
    raw = state.get("image_path")
    if not raw and isinstance(input, dict):
        for k in ("image", "path", "file", "image_path"):
            v = input.get(k)
            if isinstance(v, str) and v.strip():
                raw = v
                break
    if not raw and isinstance(input, str) and _looks_like_image_path(input):
        raw = input
    if not raw:
        raise AdapterError("vision hop needs an image path (input['image'] or state image_path)")
    path = Path(str(raw)).expanduser()
    if not path.is_file():
        raise AdapterError(f"image file not found: {path}")
    return path.resolve()


def stash_vision(input: Any, state: StateStore) -> tuple[Path, str]:
    path = image_path_from(input, state)
    question = question_from(input, state)
    state.set("image_path", str(path))
    if question:
        state.set("question", question)
    return path, question


def open_image(path: Path):
    try:
        from PIL import Image
    except ImportError as e:
        raise AdapterError("Pillow is required for vision. pip install Pillow") from e
    img = Image.open(path).convert("RGB")
    return img


def _looks_like_image_path(s: str) -> bool:
    lower = s.lower()
    if lower.startswith(("http://", "https://", "img://", "audio://")):
        return False
    return Path(s).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
