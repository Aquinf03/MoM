"""Assemble a production ModelDirectory + graphs from Settings."""

from __future__ import annotations

from mom.adapters.anthropic_chat import AnthropicChatModel
from mom.adapters.local_caption import LocalCaptionModel
from mom.adapters.local_chat import LocalChatModel
from mom.adapters.local_embed import LocalEmbedModel
from mom.adapters.local_router import LocalRouterModel
from mom.adapters.local_torchvision import LocalTorchVisionModel
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
ID_VISION_CAPTION = "prod.vision.caption"
ID_VISION_TORCH = "prod.vision.torch"
ID_ANTHROPIC = "prod.chat.anthropic"


def build_directory(settings: Settings | None = None) -> ModelDirectory:
    """Register production adapters. Default: local HF / path weights."""
    settings = settings or Settings.from_env()
    setup_logging(level=settings.log_level, json_logs=settings.log_json)
    if settings.backend == "local":
        directory = _build_local_directory(settings)
    else:
        directory = _build_http_directory(settings)

    if settings.include_stubs:
        try:
            from models import register_builtins

            register_builtins(directory)
            log.info("merged stub catalog into production directory")
        except Exception as e:  # noqa: BLE001
            log.warning("include_stubs set but models package unavailable: %s", e)

    log.info(
        "production directory ready models=%s backend=%s weights_dir=%s",
        directory.ids(),
        settings.backend,
        settings.weights_dir,
    )
    return directory


def _build_local_directory(settings: Settings) -> ModelDirectory:
    directory = ModelDirectory()
    directory.register(
        ID_CHAT_FAST,
        lambda: LocalChatModel(
            settings.chat_fast_source,
            settings=settings,
            model_id=ID_CHAT_FAST,
            system="Answer briefly in one short sentence.",
            # SLM hop: hard cap so speculate hits are actually cheap vs strong.
            max_new_tokens=min(48, settings.max_new_tokens),
        ),
        tags={"generator", "chat", "production", "local"},
        modality="text",
        vendor="huggingface",
        latency_class="small",
    )
    directory.register(
        ID_CHAT_STRONG,
        lambda: LocalChatModel(
            settings.chat_strong_source,
            settings=settings,
            model_id=ID_CHAT_STRONG,
            system="You are a careful, thorough assistant. Prefer correct detailed answers.",
            max_new_tokens=settings.max_new_tokens,
        ),
        tags={"generator", "chat", "production", "local"},
        modality="text",
        vendor="huggingface",
        latency_class="large",
    )
    directory.register(
        ID_ROUTER,
        lambda: LocalRouterModel(
            candidates=(ID_CHAT_FAST, ID_CHAT_STRONG),
            settings=settings,
            model_id=ID_ROUTER,
            default_route=ID_CHAT_FAST,
            source=settings.router_source,
        ),
        tags={"router", "production", "local"},
        modality="text",
        latency_class="cheap",
    )
    directory.register(
        ID_EMBED,
        lambda: LocalEmbedModel(
            settings.embed_source,
            settings=settings,
            model_id=ID_EMBED,
        ),
        tags={"embedder", "production", "local"},
        modality="embedding",
        vendor="huggingface",
    )
    directory.register(
        ID_VISION_CAPTION,
        lambda: LocalCaptionModel(
            settings.vision_caption_source,
            settings=settings,
            model_id=ID_VISION_CAPTION,
        ),
        tags={"vision", "caption", "production", "local"},
        modality="vision",
        vendor="huggingface",
        latency_class="medium",
    )
    directory.register(
        ID_VISION_TORCH,
        lambda: LocalTorchVisionModel(
            settings.vision_torch_name,
            settings=settings,
            model_id=ID_VISION_TORCH,
        ),
        tags={"vision", "classifier", "production", "local", "torchvision"},
        modality="vision",
        vendor="torchvision",
        latency_class="small",
    )
    return directory


def _build_http_directory(settings: Settings) -> ModelDirectory:
    """Optional external APIs — not the primary MoM path."""
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
        tags={"generator", "chat", "production", "http"},
        modality="text",
        vendor="openai-compatible",
        latency_class="small",
    )
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
            tags={"generator", "chat", "production", "http"},
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
        tags={"router", "production", "http"},
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
        tags={"embedder", "production", "http"},
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
    caption_chat = (
        Graph()
        .add("caption", ID_VISION_CAPTION)
        .add("router", ID_ROUTER)
        .add("gen", ID_CHAT_FAST)
        .link("caption", "router")
        .speculate("router", "gen")
    )
    torch_chat = (
        Graph()
        .add("vision", ID_VISION_TORCH)
        .add("router", ID_ROUTER)
        .add("gen", ID_CHAT_FAST)
        .link("vision", "router")
        .speculate("router", "gen")
    )
    vision_stack = (
        Graph()
        .add("vision", ID_VISION_TORCH)
        .add("caption", ID_VISION_CAPTION)
        .add("router", ID_ROUTER)
        .add("gen", ID_CHAT_FAST)
        .link("vision", "caption")
        .link("caption", "router")
        .speculate("router", "gen")
    )
    reg.register(
        GraphSpec(
            name="caption_chat",
            graph=caption_chat,
            shape="vision+speculate",
            requires=frozenset({ID_VISION_CAPTION, ID_ROUTER, ID_CHAT_FAST, ID_CHAT_STRONG}),
            latency_hideable=True,
            description="BLIP caption → prod router ∥ speculate(fast); miss → strong",
            tags=frozenset({"vision", "chat", "production", "hideable"}),
        )
    )
    reg.register(
        GraphSpec(
            name="torch_chat",
            graph=torch_chat,
            shape="vision+speculate",
            requires=frozenset({ID_VISION_TORCH, ID_ROUTER, ID_CHAT_FAST, ID_CHAT_STRONG}),
            latency_hideable=True,
            description="torchvision ResNet → router ∥ speculate(fast); miss → strong",
            tags=frozenset({"vision", "torchvision", "chat", "production", "hideable"}),
        )
    )
    reg.register(
        GraphSpec(
            name="vision_stack",
            graph=vision_stack,
            shape="vision+speculate",
            requires=frozenset(
                {ID_VISION_TORCH, ID_VISION_CAPTION, ID_ROUTER, ID_CHAT_FAST, ID_CHAT_STRONG}
            ),
            latency_hideable=True,
            description="torchvision → BLIP caption → speculate chat",
            tags=frozenset({"vision", "torchvision", "chat", "production"}),
        )
    )
    reg.register(
        GraphSpec(
            name="direct_caption",
            graph=Graph().add("caption", ID_VISION_CAPTION),
            shape="single",
            requires=frozenset({ID_VISION_CAPTION}),
            latency_hideable=True,
            description="BLIP caption only",
            tags=frozenset({"vision", "production"}),
        )
    )
    reg.register(
        GraphSpec(
            name="direct_torch",
            graph=Graph().add("vision", ID_VISION_TORCH),
            shape="single",
            requires=frozenset({ID_VISION_TORCH}),
            latency_hideable=True,
            description="torchvision classifier only",
            tags=frozenset({"vision", "torchvision", "production"}),
        )
    )
    caption_strong = (
        Graph()
        .add("caption", ID_VISION_CAPTION)
        .add("gen", ID_CHAT_STRONG)
        .link("caption", "gen")
    )
    torch_strong = (
        Graph()
        .add("vision", ID_VISION_TORCH)
        .add("gen", ID_CHAT_STRONG)
        .link("vision", "gen")
    )
    reg.register(
        GraphSpec(
            name="caption_strong",
            graph=caption_strong,
            shape="vision+single",
            requires=frozenset({ID_VISION_CAPTION, ID_CHAT_STRONG}),
            latency_hideable=False,
            description="BLIP caption → always strong chat",
            tags=frozenset({"vision", "chat", "production", "baseline"}),
        )
    )
    reg.register(
        GraphSpec(
            name="torch_strong",
            graph=torch_strong,
            shape="vision+single",
            requires=frozenset({ID_VISION_TORCH, ID_CHAT_STRONG}),
            latency_hideable=False,
            description="torchvision → always strong chat",
            tags=frozenset({"vision", "torchvision", "chat", "production", "baseline"}),
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
