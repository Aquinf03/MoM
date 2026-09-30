"""Tests for Hugging Face / path weight resolution + local adapters."""

from __future__ import annotations

from pathlib import Path

import pytest

from mom.adapters.local_chat import LocalChatModel
from mom.adapters.local_embed import LocalEmbedModel
from mom.adapters.local_router import LocalRouterModel
from mom.config import Settings
from mom.errors import ConfigError
from mom.health import health_check, readiness_check
from mom.runtime import ID_CHAT_FAST, ID_CHAT_STRONG, build_directory, build_registry
from mom.state import StateStore
from mom.weights import cache_dir_for, looks_like_hf_id, looks_like_path, resolve_source


def test_looks_like_hf_and_path(tmp_path: Path):
    assert looks_like_hf_id("HuggingFaceTB/SmolLM2-135M-Instruct")
    assert not looks_like_hf_id("./weights/foo")
    p = tmp_path / "model"
    p.mkdir()
    assert looks_like_path(str(p))
    assert looks_like_path("./relative")


def test_resolve_path(tmp_path: Path):
    model_dir = tmp_path / "weights" / "mine"
    model_dir.mkdir(parents=True)
    got = resolve_source(str(model_dir), tmp_path / "cache")
    assert got == model_dir.resolve()


def test_resolve_hf_uses_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dest = cache_dir_for("org/tiny", tmp_path)
    dest.mkdir(parents=True)
    (dest / "config.json").write_text("{}", encoding="utf-8")

    def _boom(*_a, **_k):
        raise AssertionError("should not download when cached")

    monkeypatch.setattr("mom.weights.hf_download", _boom)
    got = resolve_source("org/tiny", tmp_path)
    assert got == dest.resolve()


def test_resolve_bad_source(tmp_path: Path):
    with pytest.raises(ConfigError):
        resolve_source("not a valid source", tmp_path)


class _FakeCausal:
    def generate(self, messages, *, max_new_tokens=None, cancel=None):
        last = messages[-1]["content"] if messages else ""
        return f"echo:{last}"


class _FakeEmbed:
    def embed(self, text, *, cancel=None):
        return [0.1, 0.2, 0.3]


def test_local_chat_with_injected_engine():
    model = LocalChatModel("fake/source", model_id="prod.chat.fast", engine=_FakeCausal())
    out = model.run("hi", StateStore())
    assert out["text"] == "echo:hi"
    assert out["backend"] == "local"
    assert out["model"] == "prod.chat.fast"


def test_local_embed_with_injected_engine():
    model = LocalEmbedModel("fake/embed", engine=_FakeEmbed())
    out = model.run("vec", StateStore())
    assert out["dims"] == 3
    assert out["backend"] == "local"


def test_local_router_heuristic():
    router = LocalRouterModel(candidates=(ID_CHAT_FAST, ID_CHAT_STRONG))
    st = StateStore()
    st.set("classification", "hard")
    out = router.run("x", st)
    assert out["route"] == ID_CHAT_STRONG
    assert out["reason"] == "heuristic"


def test_build_directory_local_default(tmp_path: Path):
    settings = Settings(
        backend="local",
        weights_dir=tmp_path,
        chat_fast_source="org/fast",
        chat_strong_source="org/strong",
        embed_source="org/embed",
    )
    d = build_directory(settings)
    assert ID_CHAT_FAST in d
    assert ID_CHAT_STRONG in d
    assert "prod.router" in d
    assert "prod.embed" in d
    # factories are Local*
    fast = d.create(ID_CHAT_FAST)
    assert isinstance(fast, LocalChatModel)
    assert fast.source == "org/fast"
    reg = build_registry(d)
    assert "speculate_chat" in reg.available_names(d)
    h = health_check(d, settings)
    assert h["backend"] == "local"
    assert h["models"] >= 3


def test_readiness_local_hub_ids(tmp_path: Path):
    settings = Settings(
        backend="local",
        weights_dir=tmp_path,
        chat_fast_source="org/fast",
        chat_strong_source="org/strong",
        embed_source="org/embed",
    )
    d = build_directory(settings)
    body = readiness_check(d, settings)
    assert body["ready"] is True
    assert body["upstream"]["ok"] is True
