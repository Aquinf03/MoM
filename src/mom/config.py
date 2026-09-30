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


@dataclass(frozen=True)
class Settings:
    """
    Production settings. Load via `Settings.from_env()`.

    Prefer local OpenAI-compatible servers (Ollama / vLLM) for colocated latency;
    cloud keys are optional fallbacks behind the same adapters.
    """

    weights_dir: Path = field(default_factory=lambda: Path("./weights"))
    prefer_local: bool = True
    log_level: str = "INFO"
    log_json: bool = False

    # HTTP / adapters
    http_timeout_s: float = 60.0
    http_connect_timeout_s: float = 10.0
    http_max_retries: int = 2

    # OpenAI-compatible (OpenAI cloud OR Ollama/vLLM)
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_chat_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    # Local OpenAI-compatible (Ollama default)
    local_openai_base_url: str = "http://127.0.0.1:11434/v1"
    local_openai_api_key: str = "ollama"
    local_chat_model: str = "llama3.2"
    local_embed_model: str = "nomic-embed-text"

    # Anthropic
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
        return cls(
            weights_dir=weights,
            prefer_local=_env_bool("MOM_PREFER_LOCAL", True),
            log_level=(_env("MOM_LOG_LEVEL", "INFO") or "INFO").upper(),
            log_json=_env_bool("MOM_LOG_JSON", False),
            http_timeout_s=_env_float("MOM_HTTP_TIMEOUT_S", 60.0),
            http_connect_timeout_s=_env_float("MOM_HTTP_CONNECT_TIMEOUT_S", 10.0),
            http_max_retries=_env_int("MOM_HTTP_MAX_RETRIES", 2),
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
            raise ConfigError("OPENAI_API_KEY is required when MOM_PREFER_LOCAL=0")
        return self.openai_api_key

    def chat_endpoint(self) -> tuple[str, str, str]:
        """Return (base_url, api_key, model) for chat."""
        if self.prefer_local:
            return self.local_openai_base_url, self.local_openai_api_key, self.local_chat_model
        key = self.require_openai()
        return self.openai_base_url, key, self.openai_chat_model

    def embed_endpoint(self) -> tuple[str, str, str]:
        if self.prefer_local:
            return self.local_openai_base_url, self.local_openai_api_key, self.local_embed_model
        key = self.require_openai()
        return self.openai_base_url, key, self.openai_embed_model
