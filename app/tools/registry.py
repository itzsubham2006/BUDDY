"""
Tool registry.

A single place where all available tools are registered and can be looked
up by name. The orchestrator and the LLM-facing "choose_tool" schema both
go through this registry rather than importing individual tools directly,
so adding a new tool never requires touching orchestrator code.
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional

from app.tools.base import Tool

logger = logging.getLogger("jarvis.tools.registry")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool
        logger.debug("Registered tool '%s' (permission=%s)", tool.name, tool.permission_level.name)

    def register_all(self, tools: Iterable[Tool]) -> None:
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def require(self, name: str) -> Tool:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"No such tool registered: '{name}'")
        return tool

    def all_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def schemas(self) -> list[dict]:
        """Return LLM-facing schemas for every registered tool."""
        return [tool.to_schema() for tool in self._tools.values()]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)
