"""Resolve model sources: local filesystem path OR Hugging Face Hub id."""

from __future__ import annotations

import re
from pathlib import Path

from mom.errors import ConfigError
from mom.logging_config import get_logger

log = get_logger("mom.weights")

_HF_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9._-]+)+$")


def looks_like_path(source: str) -> bool:
    s = source.strip()
    if not s:
        return False
    if s.startswith(("~", "./", "../", "/")):
        return True
    # Windows drive
    if len(s) >= 3 and s[1] == ":" and s[2] in ("/", "\\"):
        return True
    p = Path(s).expanduser()
    return p.exists()


def looks_like_hf_id(source: str) -> bool:
    s = source.strip()
    return bool(_HF_ID.match(s)) and not looks_like_path(s)


def cache_dir_for(repo_id: str, weights_dir: Path) -> Path:
    """Stable on-disk layout under MOM_WEIGHTS_DIR for a Hub id."""
    safe = repo_id.strip().replace("/", "--")
    return (weights_dir / "hub" / safe).resolve()


def resolve_source(
    source: str,
    weights_dir: Path,
    *,
    token: str | None = None,
    revision: str | None = None,
    download: bool = True,
) -> Path:
    """
    Turn a source string into a local directory of weights.

    - Existing path / explicit path → that directory (must exist).
    - `org/name` Hub id → snapshot under `weights_dir/hub/org--name`.
    """
    raw = (source or "").strip()
    if not raw:
        raise ConfigError("model source is empty")

    weights_dir = Path(weights_dir).expanduser().resolve()
    weights_dir.mkdir(parents=True, exist_ok=True)

    if looks_like_path(raw) or (not looks_like_hf_id(raw) and Path(raw).expanduser().exists()):
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise ConfigError(f"model path does not exist: {path}")
        return path

    if not looks_like_hf_id(raw):
        raise ConfigError(
            f"model source must be a filesystem path or Hugging Face id (org/name), got {raw!r}"
        )

    dest = cache_dir_for(raw, weights_dir)
    if dest.exists() and any(dest.iterdir()):
        log.debug("using cached weights %s → %s", raw, dest)
        return dest

    if not download:
        raise ConfigError(f"weights not cached for {raw!r} at {dest} (download=False)")

    return hf_download(raw, dest, token=token, revision=revision)


def hf_download(
    repo_id: str,
    dest: Path,
    *,
    token: str | None = None,
    revision: str | None = None,
) -> Path:
    """Download a Hub repo into `dest` (idempotent)."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError as e:
        raise ConfigError(
            "huggingface_hub is required to pull Hub models. "
            "Install: pip install 'mom[local]' or pip install huggingface_hub"
        ) from e

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("downloading Hugging Face model %s → %s", repo_id, dest)
    path = snapshot_download(
        repo_id=repo_id,
        local_dir=str(dest),
        token=token,
        revision=revision,
    )
    return Path(path).resolve()


def ensure_resolved(
    source: str,
    weights_dir: Path,
    *,
    token: str | None = None,
    revision: str | None = None,
) -> Path:
    """Resolve without requiring the engine stack — used by readiness checks."""
    return resolve_source(source, weights_dir, token=token, revision=revision, download=False)
