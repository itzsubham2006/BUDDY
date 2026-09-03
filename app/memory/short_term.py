"""Short-term (in-process) conversation memory."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from app.llm.models import Message


@dataclass
class ShortTermMemory:
    """Keeps the last N conversation messages in memory (not persisted)."""

    max_messages: int = 20

    def __post_init__(self) -> None:
        self._messages: deque[Message] = deque(maxlen=self.max_messages)

    def add(self, role: str, content: str) -> None:
        self._messages.append(Message(role=role, content=content))  # type: ignore[arg-type]

    def add_user(self, content: str) -> None:
        self.add("user", content)

    def add_assistant(self, content: str) -> None:
        self.add("assistant", content)

    def history(self) -> list[Message]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)
