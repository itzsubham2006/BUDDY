"""
Base interface every Jarvis tool implements.

A "tool" is a single discrete capability (open an app, search the web,
change volume, ...). Tools are deliberately dumb: they don't decide
whether they're allowed to run (that's the permission system) and they
don't talk to the LLM. They just validate their own arguments and do one
thing.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Optional

from app.security.permissions import PermissionLevel


@dataclass
class ToolResult:
    """Structured result every tool.execute() must return."""

    success: bool
    message: str = ""
    error: Optional[str] = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "error": self.error,
            "data": self.data,
        }

    @classmethod
    def ok(cls, message: str = "", **data: Any) -> "ToolResult":
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(cls, error: str, message: str = "") -> "ToolResult":
        return cls(success=False, message=message or error, error=error)


@dataclass
class ToolParameter:
    """Describes a single parameter a tool accepts, for LLM tool-schemas."""

    name: str
    type: str  # "string" | "number" | "boolean" | "integer"
    description: str
    required: bool = True
    enum: Optional[list[str]] = None
    default: Any = None


class Tool(abc.ABC):
    """Abstract base class every concrete tool must subclass."""

    name: str
    description: str
    permission_level: PermissionLevel
    parameters: list[ToolParameter] = []

    def validate_arguments(self, arguments: dict[str, Any]) -> Optional[str]:
        """
        Validate arguments before execute() is called.

        Returns an error string if invalid, or None if valid. Default
        implementation checks required parameters are present; subclasses
        can extend this for deeper validation.
        """
        for param in self.parameters:
            if param.required and param.name not in arguments:
                return f"Missing required argument '{param.name}' for tool '{self.name}'"
            if param.enum and param.name in arguments:
                if arguments[param.name] not in param.enum:
                    return (
                        f"Invalid value for '{param.name}': must be one of {param.enum}"
                    )
        return None

    @abc.abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute the tool. Must not raise for expected failure modes —
        catch them and return ToolResult.fail(...) instead. Unexpected
        exceptions should still be allowed to propagate so the
        orchestrator's outer handler can log them."""
        raise NotImplementedError

    def to_schema(self) -> dict[str, Any]:
        """Return an LLM-tool-call-style schema for this tool."""
        properties = {}
        required = []
        for p in self.parameters:
            prop: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }
