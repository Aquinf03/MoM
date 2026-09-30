"""Environment-backed settings for production deployments."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from mom.errors import ConfigError


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return v.strip()


def _env_bool(name: str, default: bool = False) -> bool:
    v = _env(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    v = _env(name)
    if v is None:
        return default
    try:
        return float(v)
    except ValueError as e:
        raise ConfigError(f"env {name} must be a float, got {v!r}") from e


def _env_int(name: str, default: int) -> int:
    v = _env(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError as e:
        raise ConfigError(f"env {name} must be an int, got {v!r}") from e


# Sensible small defaults — Hub ids; override with paths anytime.
_DEFAULT_FAST = "HuggingFaceTB/SmolLM2-135M-Instruct"
_DEFAULT_STRONG = "HuggingFaceTB/SmolLM2-360M-Instruct"
_DEFAULT_EMBED = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass(frozen=True)
class Settings:
    """
    Production settings. Load via `Settings.from_env()`.

    Primary backend is **local**: Hugging Face Hub ids or filesystem paths
    under `weights_dir`. Optional `backend=http` keeps OpenAI-compatible /
    Anthropic adapters for external APIs.
    """

    weights_dir: Path = field(default_factory=lambda: Path("./weights"))
    backend: str = "local"  # local | http
    log_level: str = "INFO"
    log_json: bool = False

    # Local / HF sources (Hub id OR path)
    chat_fast_source: str = _DEFAULT_FAST
    chat_strong_source: str = _DEFAULT_STRONG
    embed_source: str = _DEFAULT_EMBED
    router_source: str | None = None  # None → heuristic-only router
    hf_token: str | None = None
    hf_revision: str | None = None
    device: str = "auto"
    dtype: str = "auto"
    max_new_tokens: int = 256

    # HTTP / adapters (optional backend=http)
    http_timeout_s: float = 60.0
    http_connect_timeout_s: float = 10.0
    http_max_retries: int = 2
    prefer_local: bool = True  # only for backend=http
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_chat_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    local_openai_base_url: str = "http://127.0.0.1:11434/v1"
    local_openai_api_key: str = "ollama"
    local_chat_model: str = "llama3.2"
    local_embed_model: str = "nomic-embed-text"
    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-3-5-haiku-latest"
    anthropic_version: str = "2023-06-01"

    # Serving
    host: str = "0.0.0.0"
    port: int = 8080
    max_runs: int = 32
    max_model_workers: int = 64
    acquire_timeout_s: float = 5.0
    default_graph: str = "speculate_chat"
    include_stubs: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        weights = Path(_env("MOM_WEIGHTS_DIR", "./weights") or "./weights")
        backend = (_env("MOM_BACKEND", "local") or "local").lower()
        if backend not in ("local", "http"):
            raise ConfigError(f"MOM_BACKEND must be 'local' or 'http', got {backend!r}")
        return cls(
            weights_dir=weights,
            backend=backend,
            log_level=(_env("MOM_LOG_LEVEL", "INFO") or "INFO").upper(),
            log_json=_env_bool("MOM_LOG_JSON", False),
            chat_fast_source=_env("MOM_CHAT_FAST", _DEFAULT_FAST) or _DEFAULT_FAST,
            chat_strong_source=_env("MOM_CHAT_STRONG", _DEFAULT_STRONG) or _DEFAULT_STRONG,
            embed_source=_env("MOM_EMBED", _DEFAULT_EMBED) or _DEFAULT_EMBED,
            router_source=_env("MOM_ROUTER"),
            hf_token=_env("HF_TOKEN") or _env("HUGGING_FACE_HUB_TOKEN"),
            hf_revision=_env("MOM_HF_REVISION"),
            device=(_env("MOM_DEVICE", "auto") or "auto").lower(),
            dtype=(_env("MOM_DTYPE", "auto") or "auto").lower(),
            max_new_tokens=_env_int("MOM_MAX_NEW_TOKENS", 256),
            http_timeout_s=_env_float("MOM_HTTP_TIMEOUT_S", 60.0),
            http_connect_timeout_s=_env_float("MOM_HTTP_CONNECT_TIMEOUT_S", 10.0),
            http_max_retries=_env_int("MOM_HTTP_MAX_RETRIES", 2),
            prefer_local=_env_bool("MOM_PREFER_LOCAL", True),
            openai_api_key=_env("OPENAI_API_KEY"),
            openai_base_url=_env("OPENAI_BASE_URL", "https://api.openai.com/v1")
            or "https://api.openai.com/v1",
            openai_chat_model=_env("OPENAI_CHAT_MODEL", "gpt-4o-mini") or "gpt-4o-mini",
            openai_embed_model=_env("OPENAI_EMBED_MODEL", "text-embedding-3-small")
            or "text-embedding-3-small",
            local_openai_base_url=_env("MOM_LOCAL_OPENAI_BASE_URL", "http://127.0.0.1:11434/v1")
            or "http://127.0.0.1:11434/v1",
            local_openai_api_key=_env("MOM_LOCAL_OPENAI_API_KEY", "ollama") or "ollama",
            local_chat_model=_env("MOM_LOCAL_CHAT_MODEL", "llama3.2") or "llama3.2",
            local_embed_model=_env("MOM_LOCAL_EMBED_MODEL", "nomic-embed-text")
            or "nomic-embed-text",
            anthropic_api_key=_env("ANTHROPIC_API_KEY"),
            anthropic_base_url=_env("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
            or "https://api.anthropic.com",
            anthropic_model=_env("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
            or "claude-3-5-haiku-latest",
            anthropic_version=_env("ANTHROPIC_VERSION", "2023-06-01") or "2023-06-01",
            host=_env("MOM_HOST", "0.0.0.0") or "0.0.0.0",
            port=_env_int("MOM_PORT", 8080),
            max_runs=_env_int("MOM_MAX_RUNS", 32),
            max_model_workers=_env_int("MOM_MAX_MODEL_WORKERS", 64),
            acquire_timeout_s=_env_float("MOM_ACQUIRE_TIMEOUT_S", 5.0),
            default_graph=_env("MOM_DEFAULT_GRAPH", "speculate_chat") or "speculate_chat",
            include_stubs=_env_bool("MOM_INCLUDE_STUBS", False),
        )

    def require_openai(self) -> str:
        if self.prefer_local:
            return self.local_openai_api_key
        if not self.openai_api_key:
            raise ConfigError("OPENAI_API_KEY is required when MOM_BACKEND=http and MOM_PREFER_LOCAL=0")
        return self.openai_api_key

    def chat_endpoint(self) -> tuple[str, str, str]:
        """Return (base_url, api_key, model) for HTTP chat backend."""
        if self.prefer_local:
            return self.local_openai_base_url, self.local_openai_api_key, self.local_chat_model
        key = self.require_openai()
        return self.openai_base_url, key, self.openai_chat_model

    def embed_endpoint(self) -> tuple[str, str, str]:
        if self.prefer_local:
            return self.local_openai_base_url, self.local_openai_api_key, self.local_embed_model
        key = self.require_openai()
        return self.openai_base_url, key, self.openai_embed_model
