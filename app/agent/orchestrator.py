"""
AgentOrchestrator: the control center of Jarvis.

Pipeline per spec section 6:
1. Receive user text
2. Understand intent (delegated to the LLM via choose_tool)
3. Determine whether a tool is required
4. Select the correct tool
5. Validate tool arguments
6. Check permissions
7. Request confirmation when required
8. Execute the tool
9. Process the result
10. Generate a natural-language response

The LLM is never trusted to enforce permissions or confirmations itself —
those checks always happen here, outside the LLM's control.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.agent.planner import Planner
from app.agent.prompts import build_confirmation_summary, build_system_prompt
from app.agent.state import TurnState, TurnStatus
from app.llm.client import LLMClient, LLMError
from app.llm.models import Message
from app.memory.long_term import LongTermMemory
from app.memory.short_term import ShortTermMemory
from app.security.confirmations import ConfirmationManager, ConfirmationRequest
from app.security.permissions import PermissionChecker
from app.tools.registry import ToolRegistry

logger = logging.getLogger("jarvis.agent.orchestrator")


class AgentOrchestrator:
    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        permission_checker: PermissionChecker,
        short_term_memory: ShortTermMemory,
        long_term_memory: LongTermMemory,
        confirmation_manager: Optional[ConfirmationManager] = None,
        agent_name: str = "Jarvis",
    ) -> None:
        self._llm = llm_client
        self._registry = tool_registry
        self._permissions = permission_checker
        self._short_term = short_term_memory
        self._long_term = long_term_memory
        self._confirmations = confirmation_manager
        self._planner = Planner(tool_registry)
        self._agent_name = agent_name

    async def handle_user_text(self, user_text: str) -> TurnState:
        """Process one user utterance end-to-end and return the final TurnState."""
        turn = TurnState(user_text=user_text)
        self._short_term.add_user(user_text)
        logger.info("User turn received: %s", _truncate(user_text))

        try:
            response = await self._llm.choose_tool(
                messages=self._short_term.history(),
                tool_schemas=self._registry.schemas(),
                system_prompt=build_system_prompt(self._agent_name, self._long_term.all()),
            )
        except LLMError as exc:
            return self._fail(turn, f"I'm having trouble reaching my language model: {exc}")

        plan = self._planner.plan_from_llm_response(response)

        if plan.validation_error:
            return self._fail(turn, f"I couldn't do that: {plan.validation_error}")

        if plan.tool_name is None:
            turn.status = TurnStatus.RESPONDED
            turn.final_response = plan.direct_response or "I'm not sure how to help with that."
            self._short_term.add_assistant(turn.final_response)
            return turn

        turn.selected_tool = plan.tool_name
        turn.tool_arguments = plan.arguments
        turn.status = TurnStatus.TOOL_SELECTED
        logger.info("Selected tool=%s arguments=%s", plan.tool_name, plan.arguments)

        tool = self._registry.require(plan.tool_name)

        if not self._permissions.is_allowed(tool.name, tool.permission_level):
            return self._fail(turn, f"I'm not allowed to do that ({tool.name}).")

        if self._permissions.requires_confirmation(tool.name, tool.permission_level):
            if self._confirmations is None:
                return self._fail(
                    turn,
                    f"'{tool.name}' requires confirmation but no confirmation channel "
                    "is configured, so I won't proceed.",
                )
            turn.status = TurnStatus.AWAITING_CONFIRMATION
            request = ConfirmationRequest(
                tool_name=tool.name,
                summary=build_confirmation_summary(tool.name, plan.arguments),
                arguments=plan.arguments,
            )
            result = await self._confirmations.request_confirmation(request)
            if not result.confirmed:
                turn.final_response = "Okay, I won't do that."
                turn.status = TurnStatus.RESPONDED
                self._short_term.add_assistant(turn.final_response)
                logger.info("User declined confirmation for tool=%s", tool.name)
                return turn

        try:
            tool_result = await tool.execute(plan.arguments)
        except Exception as exc:  # noqa: BLE001 - tool crashed unexpectedly
            logger.exception("Tool '%s' raised an unexpected exception", tool.name)
            return self._fail(turn, f"Something went wrong while running '{tool.name}'.")

        turn.tool_result = tool_result.to_dict()
        turn.status = TurnStatus.EXECUTED
        logger.info("Tool '%s' result: success=%s", tool.name, tool_result.success)

        turn.final_response = self._summarize_result(tool.name, tool_result)
        turn.status = TurnStatus.RESPONDED
        self._short_term.add_assistant(turn.final_response)
        return turn

    def _summarize_result(self, tool_name: str, tool_result) -> str:  # type: ignore[no-untyped-def]
        if tool_result.success:
            return tool_result.message or "Done."
        return tool_result.message or f"I couldn't complete '{tool_name}'."

    def _fail(self, turn: TurnState, message: str) -> TurnState:
        turn.status = TurnStatus.FAILED
        turn.error = message
        turn.final_response = message
        self._short_term.add_assistant(message)
        logger.warning("Turn failed: %s", message)
        return turn


def _truncate(text: str, length: int = 120) -> str:
    return text if len(text) <= length else text[: length - 3] + "..."
