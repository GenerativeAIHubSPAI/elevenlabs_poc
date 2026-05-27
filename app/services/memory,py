# app/services/memory.py

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

conversation_store: dict[str, list[dict[str, Any]]] = defaultdict(list)


def add_turn(
    conversation_key: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    conversation_store[conversation_key].append(
        {
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


def get_history(
    conversation_key: str,
    max_turns: int = 8,
) -> list[dict[str, Any]]:
    history = conversation_store.get(conversation_key, [])

    if max_turns <= 0:
        return []

    return history[-max_turns:]


def format_history(
    conversation_key: str,
    max_turns: int = 8,
) -> str:
    history = get_history(
        conversation_key=conversation_key,
        max_turns=max_turns,
    )

    if not history:
        return ""

    return "\n".join(
        f"{item['role'].upper()}: {item['content']}"
        for item in history
    )


def clear_session(conversation_key: str) -> None:
    conversation_store.pop(conversation_key, None)