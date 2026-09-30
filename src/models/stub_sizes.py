"""Size / vendor variants of generator stubs — still one Model.run contract."""

from __future__ import annotations

from models.stub_llm import LlmModel
from models.stub_slm import SlmModel
from mom.directory import ModelDirectory


def register(directory: ModelDirectory) -> None:
    directory.register(
        "stub.slm.tiny",
        lambda: SlmModel(delay_ms=12.0),
        tags={"stub", "generator", "slm", "local"},
        latency_class="tiny",
        modality="text",
        vendor="local",
        size="tiny",
    )
    directory.register(
        "stub.llm.medium",
        lambda: LlmModel(delay_ms=55.0),
        tags={"stub", "generator", "llm", "local"},
        latency_class="medium",
        modality="text",
        vendor="local",
        size="medium",
    )
    directory.register(
        "stub.llm.xlarge",
        lambda: LlmModel(delay_ms=150.0),
        tags={"stub", "generator", "llm", "cloud"},
        latency_class="xlarge",
        modality="text",
        vendor="cloud",
        size="xlarge",
    )
    # Vendor-flavored aliases (same stubs; composition still uses directory ids)
    directory.register(
        "stub.local.phi",
        lambda: SlmModel(delay_ms=25.0),
        tags={"stub", "generator", "slm", "local"},
        latency_class="small",
        modality="text",
        vendor="local",
        size="small",
    )
    directory.register(
        "stub.cloud.gpt",
        lambda: LlmModel(delay_ms=100.0),
        tags={"stub", "generator", "llm", "cloud"},
        latency_class="large",
        modality="text",
        vendor="cloud",
        size="large",
    )
