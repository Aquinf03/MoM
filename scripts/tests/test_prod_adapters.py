"""Mocked HTTP tests for production adapters (no live keys required)."""

from __future__ import annotations

import httpx
import pytest
import respx

from mom.adapters.openai_chat import OpenAIChatModel
from mom.adapters.openai_embed import OpenAIEmbedModel
from mom.adapters.openai_router import OpenAIRouterModel
from mom.config import Settings
from mom.errors import AdapterAuthError, AdapterError
from mom.health import health_check
from mom.runtime import ID_CHAT_FAST, ID_CHAT_STRONG, build_directory, build_registry
from mom.state import StateStore


@pytest.fixture
def settings() -> Settings:
    return Settings(
        prefer_local=True,
        local_openai_base_url="http://llm.test/v1",
        local_openai_api_key="test-key",
        local_chat_model="test-model",
        local_embed_model="test-embed",
        http_timeout_s=5.0,
        http_max_retries=0,
    )


@respx.mock
def test_openai_chat_success(settings: Settings):
    respx.post("http://llm.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello from upstream"}}],
                "usage": {"total_tokens": 3},
            },
        )
    )
    model = OpenAIChatModel(
        base_url=settings.local_openai_base_url,
        api_key=settings.local_openai_api_key,
        model=settings.local_chat_model,
        settings=settings,
        model_id="prod.chat.fast",
    )
    out = model.run("hi", StateStore())
    assert out["text"] == "hello from upstream"
    assert out["model"] == "prod.chat.fast"


@respx.mock
def test_openai_chat_auth_error(settings: Settings):
    respx.post("http://llm.test/v1/chat/completions").mock(
        return_value=httpx.Response(401, text="nope")
    )
    model = OpenAIChatModel(
        base_url=settings.local_openai_base_url,
        api_key="bad",
        model="x",
        settings=settings,
    )
    with pytest.raises(AdapterAuthError):
        model.run("hi", StateStore())


@respx.mock
def test_openai_embed(settings: Settings):
    respx.post("http://llm.test/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2, 0.3]}]},
        )
    )
    model = OpenAIEmbedModel(
        base_url=settings.local_openai_base_url,
        api_key=settings.local_openai_api_key,
        model=settings.local_embed_model,
        settings=settings,
    )
    out = model.run("vec me", StateStore())
    assert out["dims"] == 3


def test_router_heuristic_short_circuits(settings: Settings):
    router = OpenAIRouterModel(
        base_url=settings.local_openai_base_url,
        api_key=settings.local_openai_api_key,
        model=settings.local_chat_model,
        candidates=(ID_CHAT_FAST, ID_CHAT_STRONG),
        settings=settings,
    )
    st = StateStore()
    st.set("classification", "hard")
    out = router.run("x", st)
    assert out["route"] == ID_CHAT_STRONG
    assert out["reason"] == "heuristic"


def test_build_directory_and_registry(settings: Settings, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MOM_PREFER_LOCAL", "1")
    monkeypatch.setenv("MOM_LOCAL_OPENAI_BASE_URL", "http://llm.test/v1")
    d = build_directory(settings)
    assert ID_CHAT_FAST in d
    assert ID_CHAT_STRONG in d
    reg = build_registry(d)
    assert "speculate_chat" in reg.available_names(d)
    h = health_check(d, settings)
    assert h["models"] >= 3
    assert "version" in h


@respx.mock
def test_chat_bad_shape_raises(settings: Settings):
    respx.post("http://llm.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": []})
    )
    model = OpenAIChatModel(
        base_url=settings.local_openai_base_url,
        api_key="k",
        model="m",
        settings=settings,
    )
    with pytest.raises(AdapterError):
        model.run("hi", StateStore())
