"""Conversation/turn state passed through the orchestrator pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class TurnStatus(Enum):
    RECEIVED = auto()
    TOOL_SELECTED = auto()
    AWAITING_CONFIRMATION = auto()
    EXECUTED = auto()
    RESPONDED = auto()
    FAILED = auto()


@dataclass
class TurnState:
    """Everything the orchestrator tracks while handling a single user turn."""

    user_text: str
    status: TurnStatus = TurnStatus.RECEIVED
    selected_tool: Optional[str] = None
    tool_arguments: dict[str, Any] = field(default_factory=dict)
    tool_result: Optional[dict[str, Any]] = None
    final_response: Optional[str] = None
    error: Optional[str] = None
