"""Assemble a production ModelDirectory + graphs from Settings."""

from __future__ import annotations

from mom.adapters.anthropic_chat import AnthropicChatModel
from mom.adapters.openai_chat import OpenAIChatModel
from mom.adapters.openai_embed import OpenAIEmbedModel
from mom.adapters.openai_router import OpenAIRouterModel
from mom.config import Settings
from mom.directory import ModelDirectory
from mom.graph import Graph
from mom.limits import ConcurrencyLimits
from mom.logging_config import get_logger, setup_logging
from mom.registry import GraphRegistry, GraphSpec

log = get_logger("mom.runtime")

# Production directory ids (stable contract for graphs)
ID_ROUTER = "prod.router"
ID_CHAT_FAST = "prod.chat.fast"
ID_CHAT_STRONG = "prod.chat.strong"
ID_EMBED = "prod.embed"
ID_ANTHROPIC = "prod.chat.anthropic"


def build_directory(settings: Settings | None = None) -> ModelDirectory:
    """Register real adapters. Optionally merge stub catalog for mixed demos."""
    settings = settings or Settings.from_env()
    setup_logging(level=settings.log_level, json_logs=settings.log_json)
    directory = ModelDirectory()

    base, key, chat_model = settings.chat_endpoint()
    embed_base, embed_key, embed_model = settings.embed_endpoint()

    directory.register(
        ID_CHAT_FAST,
        lambda: OpenAIChatModel(
            base_url=base,
            api_key=key,
            model=chat_model,
            settings=settings,
            model_id=ID_CHAT_FAST,
        ),
        tags={"generator", "chat", "production"},
        modality="text",
        vendor="openai-compatible",
        latency_class="small",
    )
    # Strong path: Anthropic if keyed, else same endpoint with stronger name hint
    if settings.anthropic_api_key:
        directory.register(
            ID_CHAT_STRONG,
            lambda: AnthropicChatModel(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
                base_url=settings.anthropic_base_url,
                version=settings.anthropic_version,
                settings=settings,
                model_id=ID_CHAT_STRONG,
            ),
            tags={"generator", "chat", "production", "anthropic"},
            modality="text",
            vendor="anthropic",
            latency_class="large",
        )
    else:
        directory.register(
            ID_CHAT_STRONG,
            lambda: OpenAIChatModel(
                base_url=base,
                api_key=key,
                model=chat_model,
                settings=settings,
                model_id=ID_CHAT_STRONG,
                system="You are a careful, thorough assistant. Prefer correct detailed answers.",
            ),
            tags={"generator", "chat", "production"},
            modality="text",
            vendor="openai-compatible",
            latency_class="large",
        )

    directory.register(
        ID_ROUTER,
        lambda: OpenAIRouterModel(
            base_url=base,
            api_key=key,
            model=chat_model,
            candidates=(ID_CHAT_FAST, ID_CHAT_STRONG),
            settings=settings,
            model_id=ID_ROUTER,
            default_route=ID_CHAT_FAST,
        ),
        tags={"router", "production"},
        modality="text",
        latency_class="cheap",
    )
    directory.register(
        ID_EMBED,
        lambda: OpenAIEmbedModel(
            base_url=embed_base,
            api_key=embed_key,
            model=embed_model,
            settings=settings,
            model_id=ID_EMBED,
        ),
        tags={"embedder", "production"},
        modality="embedding",
    )
    if settings.anthropic_api_key and ID_ANTHROPIC not in directory:
        directory.register(
            ID_ANTHROPIC,
            lambda: AnthropicChatModel(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
                base_url=settings.anthropic_base_url,
                version=settings.anthropic_version,
                settings=settings,
                model_id=ID_ANTHROPIC,
            ),
            tags={"generator", "chat", "production", "anthropic"},
            modality="text",
            vendor="anthropic",
        )

    if settings.include_stubs:
        try:
            from models import register_builtins

            register_builtins(directory)
            log.info("merged stub catalog into production directory")
        except Exception as e:  # noqa: BLE001
            log.warning("include_stubs set but models package unavailable: %s", e)

    log.info(
        "production directory ready models=%s prefer_local=%s",
        directory.ids(),
        settings.prefer_local,
    )
    return directory


def build_registry(directory: ModelDirectory | None = None) -> GraphRegistry:
    """Production graph shapes over prod.* ids."""
    reg = GraphRegistry()
    speculate = (
        Graph()
        .add("router", ID_ROUTER)
        .add("gen", ID_CHAT_FAST)
        .speculate("router", "gen")
    )
    reg.register(
        GraphSpec(
            name="speculate_chat",
            graph=speculate,
            shape="speculate",
            requires=frozenset({ID_ROUTER, ID_CHAT_FAST, ID_CHAT_STRONG}),
            latency_hideable=True,
            description="prod router ∥ speculate(fast); miss → strong",
            tags=frozenset({"chat", "production", "hideable"}),
        )
    )
    reg.register(
        GraphSpec(
            name="direct_fast",
            graph=Graph().add("gen", ID_CHAT_FAST),
            shape="single",
            requires=frozenset({ID_CHAT_FAST}),
            latency_hideable=True,
            description="single fast chat model",
            tags=frozenset({"chat", "production"}),
        )
    )
    reg.register(
        GraphSpec(
            name="direct_strong",
            graph=Graph().add("gen", ID_CHAT_STRONG),
            shape="single",
            requires=frozenset({ID_CHAT_STRONG}),
            latency_hideable=True,
            description="single strong chat model",
            tags=frozenset({"chat", "production"}),
        )
    )
    if directory is not None:
        missing = [s.name for s in reg.specs() if not s.satisfied_by(directory)]
        if missing:
            log.warning("graphs not satisfied by directory: %s", missing)
    return reg


def concurrency_limits(settings: Settings | None = None) -> ConcurrencyLimits:
    settings = settings or Settings.from_env()
    return ConcurrencyLimits(
        max_runs=settings.max_runs,
        max_model_workers=settings.max_model_workers,
        acquire_timeout_s=settings.acquire_timeout_s,
    )
