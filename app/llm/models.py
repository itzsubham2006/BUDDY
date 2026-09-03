"""Shared data models for the LLM abstraction layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

Role = Literal["system", "user", "assistant"]


@dataclass
class Message:
    role: Role
    content: str


@dataclass
class ToolCall:
    """A tool invocation the LLM decided to make."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: Optional[str] = None


@dataclass
class LLMResponse:
    """Normalized response shape returned by every LLM provider."""

    text: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None

    @property
    def wants_tool_call(self) -> bool:
        return len(self.tool_calls) > 0
