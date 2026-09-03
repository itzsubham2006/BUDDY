"""
Planner: translates an LLM response into a validated (tool_name, arguments)
pair, or determines that no tool call is needed.

Kept separate from the orchestrator so tool-selection logic can be tested
in isolation from execution/permissions/confirmation concerns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.llm.models import LLMResponse
from app.tools.registry import ToolRegistry

logger = logging.getLogger("jarvis.agent.planner")


@dataclass
class Plan:
    tool_name: Optional[str]
    arguments: dict
    direct_response: Optional[str]
    validation_error: Optional[str] = None


class Planner:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def plan_from_llm_response(self, response: LLMResponse) -> Plan:
        if not response.wants_tool_call:
            return Plan(tool_name=None, arguments={}, direct_response=response.text)

        # V1: act on the first requested tool call only. Multi-tool turns
        # can be added later by looping the orchestrator over a plan list.
        call = response.tool_calls[0]
        tool = self._registry.get(call.name)
        if tool is None:
            logger.warning("LLM requested unknown tool '%s'", call.name)
            return Plan(
                tool_name=None,
                arguments={},
                direct_response=None,
                validation_error=f"Unknown tool requested: '{call.name}'",
            )

        error = tool.validate_arguments(call.arguments)
        if error:
            logger.warning("Argument validation failed for '%s': %s", call.name, error)
            return Plan(
                tool_name=call.name,
                arguments=call.arguments,
                direct_response=None,
                validation_error=error,
            )

        return Plan(tool_name=call.name, arguments=call.arguments, direct_response=None)
