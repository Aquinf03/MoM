"""Multi-turn helpers — history lives in StateStore, not message-passing."""

from __future__ import annotations

from typing import Any

from mom.state import StateStore

MESSAGES_KEY = "messages"
TURN_KEY = "turn"


def get_messages(state: StateStore) -> list[dict[str, Any]]:
    """Authoritative conversation history (shared across models/turns)."""
    raw = state.get(MESSAGES_KEY)
    if raw is None:
        return []
    if not isinstance(raw, list):
        return list(raw)
    return list(raw)


def set_messages(state: StateStore, messages: list[dict[str, Any]]) -> None:
    state.set(MESSAGES_KEY, messages)
    state.set(TURN_KEY, sum(1 for m in messages if m.get("role") == "user"))


def add_user(state: StateStore, content: str) -> None:
    """Record a user turn into the shared store (call once per user input)."""
    msgs = get_messages(state)
    msgs.append({"role": "user", "content": content})
    set_messages(state, msgs)


def add_assistant(
    state: StateStore,
    content: str,
    *,
    model: str | None = None,
) -> None:
    """Record an assistant turn — written by the generating model, not handed off."""
    msgs = get_messages(state)
    entry: dict[str, Any] = {"role": "assistant", "content": content}
    if model is not None:
        entry["model"] = model
    msgs.append(entry)
    set_messages(state, msgs)


def turn_count(state: StateStore) -> int:
    """Number of user turns so far."""
    n = state.get(TURN_KEY)
    if isinstance(n, int):
        return n
    return sum(1 for m in get_messages(state) if m.get("role") == "user")


def history_text(state: StateStore, *, limit: int | None = None) -> str:
    """Flat view of recent messages for stub models that want context."""
    msgs = get_messages(state)
    if limit is not None:
        msgs = msgs[-limit:]
    parts = [f"{m.get('role', '?')}: {m.get('content', '')}" for m in msgs]
    return "\n".join(parts)
