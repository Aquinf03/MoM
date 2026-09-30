"""Typed errors for production adapters and serving."""

from __future__ import annotations


class MomError(Exception):
    """Base for all MoM SDK errors."""


class ConfigError(MomError):
    """Invalid or missing configuration."""


class AdapterError(MomError):
    """Model adapter failed (upstream, parse, or local)."""

    def __init__(self, message: str, *, model_id: str | None = None, cause: BaseException | None = None):
        super().__init__(message)
        self.model_id = model_id
        self.__cause__ = cause


class AdapterTimeout(AdapterError):
    """Upstream or local model call timed out."""


class AdapterAuthError(AdapterError):
    """Missing/invalid credentials for an upstream provider."""
