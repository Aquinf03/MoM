"""In-process model engines — load once, share across adapters."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from mom.errors import AdapterError, ConfigError
from mom.logging_config import get_logger

log = get_logger("mom.engines")

_LOCK = threading.RLock()
_CAUSAL: dict[str, Any] = {}
_EMBED: dict[str, Any] = {}


def _device_and_dtype(device: str, dtype: str) -> tuple[str, Any]:
    try:
        import torch
    except ImportError as e:
        raise ConfigError(
            "torch is required for local engines. Install: pip install 'mom[local]'"
        ) from e

    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda"
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"

    if dtype == "auto":
        if device in ("cuda", "mps"):
            torch_dtype = torch.float16
        else:
            torch_dtype = torch.float32
    elif dtype == "float16":
        torch_dtype = torch.float16
    elif dtype == "bfloat16":
        torch_dtype = torch.bfloat16
    elif dtype == "float32":
        torch_dtype = torch.float32
    else:
        raise ConfigError(f"unknown MOM_DTYPE={dtype!r}")
    return device, torch_dtype


class CausalLMEngine:
    """Causal LM via transformers — owned weights, in-process generate."""

    def __init__(
        self,
        path: Path,
        *,
        device: str = "auto",
        dtype: str = "auto",
        max_new_tokens: int = 256,
    ) -> None:
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as e:
            raise ConfigError(
                "transformers is required for local chat. Install: pip install 'mom[local]'"
            ) from e

        self.path = Path(path)
        self.max_new_tokens = max_new_tokens
        self.device, torch_dtype = _device_and_dtype(device, dtype)
        log.info("loading causal LM from %s device=%s", self.path, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.path), trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            str(self.path),
            torch_dtype=torch_dtype,
            trust_remote_code=True,
        )
        self.model.to(self.device)
        self.model.eval()
        if self.tokenizer.pad_token_id is None and self.tokenizer.eos_token_id is not None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        max_new_tokens: int | None = None,
        cancel: Any = None,
    ) -> str:
        if cancel is not None:
            cancel.check()
        tok = self.tokenizer
        if hasattr(tok, "apply_chat_template") and tok.chat_template:
            prompt = tok.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages) + "\nassistant:"
        inputs = tok(prompt, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        n = max_new_tokens if max_new_tokens is not None else self.max_new_tokens
        try:
            import torch

            with torch.inference_mode():
                out = self.model.generate(
                    **inputs,
                    max_new_tokens=n,
                    do_sample=False,
                    pad_token_id=tok.pad_token_id,
                )
        except Exception as e:  # noqa: BLE001
            raise AdapterError(f"local generate failed: {e}", cause=e) from e
        if cancel is not None:
            cancel.check()
        gen = out[0, inputs["input_ids"].shape[-1] :]
        return tok.decode(gen, skip_special_tokens=True).strip()


class EmbedEngine:
    """Sentence / feature embeddings via transformers mean-pool."""

    def __init__(self, path: Path, *, device: str = "auto", dtype: str = "auto") -> None:
        try:
            from transformers import AutoModel, AutoTokenizer
        except ImportError as e:
            raise ConfigError(
                "transformers is required for local embed. Install: pip install 'mom[local]'"
            ) from e

        self.path = Path(path)
        self.device, torch_dtype = _device_and_dtype(device, dtype)
        log.info("loading embed model from %s device=%s", self.path, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.path), trust_remote_code=True)
        self.model = AutoModel.from_pretrained(
            str(self.path),
            torch_dtype=torch_dtype,
            trust_remote_code=True,
        )
        self.model.to(self.device)
        self.model.eval()

    def embed(self, text: str, *, cancel: Any = None) -> list[float]:
        if cancel is not None:
            cancel.check()
        import torch
        import torch.nn.functional as F

        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.inference_mode():
            out = self.model(**inputs)
            # mean pool on attention mask
            last = out.last_hidden_state
            mask = inputs["attention_mask"].unsqueeze(-1).clamp(min=1)
            pooled = (last * mask).sum(dim=1) / mask.sum(dim=1)
            pooled = F.normalize(pooled, p=2, dim=1)
        if cancel is not None:
            cancel.check()
        return pooled[0].detach().cpu().tolist()


def get_causal(
    path: Path,
    *,
    device: str = "auto",
    dtype: str = "auto",
    max_new_tokens: int = 256,
) -> CausalLMEngine:
    key = str(Path(path).resolve())
    with _LOCK:
        eng = _CAUSAL.get(key)
        if eng is None:
            eng = CausalLMEngine(
                Path(key), device=device, dtype=dtype, max_new_tokens=max_new_tokens
            )
            _CAUSAL[key] = eng
        return eng


def get_embed(path: Path, *, device: str = "auto", dtype: str = "auto") -> EmbedEngine:
    key = str(Path(path).resolve())
    with _LOCK:
        eng = _EMBED.get(key)
        if eng is None:
            eng = EmbedEngine(Path(key), device=device, dtype=dtype)
            _EMBED[key] = eng
        return eng


def clear_engine_cache() -> None:
    with _LOCK:
        _CAUSAL.clear()
        _EMBED.clear()
