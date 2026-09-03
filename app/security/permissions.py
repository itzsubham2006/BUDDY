"""
Permission model for Jarvis tools.

Every tool declares a PermissionLevel. The orchestrator (never the LLM)
is responsible for checking that level before executing a tool, and for
routing HIGH/CRITICAL actions through the confirmation flow.
"""

from __future__ import annotations

from enum import IntEnum


class PermissionLevel(IntEnum):
    """Ordered permission levels. Higher = more sensitive."""

    LOW = 1       # open_application, search_web, volume control, get_time...
    MEDIUM = 2    # read files, read messages, browser interactions
    HIGH = 3      # send messages/emails, modify/delete files, shell commands
    CRITICAL = 4  # financial transactions, password/account changes

    @classmethod
    def from_string(cls, value: str) -> "PermissionLevel":
        try:
            return cls[value.strip().upper()]
        except KeyError as exc:
            raise ValueError(f"Unknown permission level: {value!r}") from exc


class PermissionDeniedError(Exception):
    """Raised when a tool call is blocked by the permission system."""


class PermissionChecker:
    """
    Central authority for whether a tool call is allowed to run, and
    whether it needs explicit user confirmation first.

    The LLM can *request* a tool call, but only this class (invoked by the
    orchestrator) decides whether it proceeds. Overrides from config allow
    an administrator to tighten or loosen individual tools, but nothing
    the LLM says can change permission decisions at runtime.
    """

    def __init__(
        self,
        overrides: dict[str, str] | None = None,
        require_confirmation_high: bool = True,
        require_confirmation_critical: bool = True,
    ) -> None:
        self._overrides: dict[str, PermissionLevel] = {
            name: PermissionLevel.from_string(level)
            for name, level in (overrides or {}).items()
        }
        self._require_confirmation_high = require_confirmation_high
        self._require_confirmation_critical = require_confirmation_critical

    def effective_level(self, tool_name: str, declared_level: PermissionLevel) -> PermissionLevel:
        """Return the level that actually applies, honoring config overrides."""
        return self._overrides.get(tool_name, declared_level)

    def requires_confirmation(self, tool_name: str, declared_level: PermissionLevel) -> bool:
        level = self.effective_level(tool_name, declared_level)
        if level == PermissionLevel.HIGH:
            return self._require_confirmation_high
        if level == PermissionLevel.CRITICAL:
            return self._require_confirmation_critical
        return False

    def is_allowed(self, tool_name: str, declared_level: PermissionLevel) -> bool:
        """
        Placeholder hook for future per-tool allow/deny lists (e.g. a user
        disabling a category of tools entirely). Currently everything
        declared in the registry is allowed to be *considered*; HIGH/
        CRITICAL tools still need confirmation via `requires_confirmation`.
        """
        return True
