from __future__ import annotations

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.state import TurnStatus
from app.llm.client import LLMClient, LLMProvider
from app.llm.models import LLMResponse, ToolCall
from app.memory.long_term import LongTermMemory
from app.memory.short_term import ShortTermMemory
from app.security.confirmations import ConfirmationManager
from app.security.permissions import PermissionChecker, PermissionLevel
from app.tools.base import Tool, ToolResult
from app.tools.registry import ToolRegistry


class EchoTimeTool(Tool):
    name = "get_current_time"
    description = "test"
    permission_level = PermissionLevel.LOW
    parameters = []

    async def execute(self, arguments):
        return ToolResult.ok(message="It is noon.")


class FailingTool(Tool):
    name = "flaky_tool"
    description = "test"
    permission_level = PermissionLevel.LOW
    parameters = []

    async def execute(self, arguments):
        raise RuntimeError("boom")


class HighRiskTool(Tool):
    name = "send_email"
    description = "test"
    permission_level = PermissionLevel.HIGH
    parameters = []

    async def execute(self, arguments):
        return ToolResult.ok(message="Email sent.")


def _client_for(provider: LLMProvider, config) -> LLMClient:
    return LLMClient(config, provider=provider)


class ToolCallProvider(LLMProvider):
    def __init__(self, config, tool_name, arguments=None):
        super().__init__(config)
        self._tool_name = tool_name
        self._arguments = arguments or {}

    async def chat(self, messages, tools=None, system_prompt=None):
        return LLMResponse(tool_calls=[ToolCall(name=self._tool_name, arguments=self._arguments)])


class DirectResponseProvider(LLMProvider):
    async def chat(self, messages, tools=None, system_prompt=None):
        return LLMResponse(text="I can't do that.")


def _make_orchestrator(tmp_settings, provider, registry, confirmation_manager=None, checker=None):
    llm = LLMClient(tmp_settings.llm, provider=provider)
    return AgentOrchestrator(
        llm_client=llm,
        tool_registry=registry,
        permission_checker=checker or PermissionChecker(),
        short_term_memory=ShortTermMemory(max_messages=10),
        long_term_memory=LongTermMemory(tmp_settings.memory_long_term_store_path),
        confirmation_manager=confirmation_manager,
        agent_name="Jarvis",
    )


@pytest.mark.asyncio
async def test_orchestrator_executes_low_permission_tool(tmp_settings):
    registry = ToolRegistry()
    registry.register(EchoTimeTool())
    provider = ToolCallProvider(tmp_settings.llm, "get_current_time")
    orch = _make_orchestrator(tmp_settings, provider, registry)

    turn = await orch.handle_user_text("what time is it")

    assert turn.status == TurnStatus.RESPONDED
    assert turn.selected_tool == "get_current_time"
    assert turn.final_response == "It is noon."


@pytest.mark.asyncio
async def test_orchestrator_direct_response_when_no_tool_needed(tmp_settings):
    registry = ToolRegistry()
    provider = DirectResponseProvider(tmp_settings.llm)
    orch = _make_orchestrator(tmp_settings, provider, registry)

    turn = await orch.handle_user_text("tell me a fact")

    assert turn.selected_tool is None
    assert turn.final_response == "I can't do that."


@pytest.mark.asyncio
async def test_orchestrator_unknown_tool_fails_gracefully(tmp_settings):
    registry = ToolRegistry()
    provider = ToolCallProvider(tmp_settings.llm, "does_not_exist")
    orch = _make_orchestrator(tmp_settings, provider, registry)

    turn = await orch.handle_user_text("do something weird")

    assert turn.status == TurnStatus.FAILED
    assert "Unknown tool" in turn.error


@pytest.mark.asyncio
async def test_orchestrator_tool_exception_does_not_crash(tmp_settings):
    registry = ToolRegistry()
    registry.register(FailingTool())
    provider = ToolCallProvider(tmp_settings.llm, "flaky_tool")
    orch = _make_orchestrator(tmp_settings, provider, registry)

    turn = await orch.handle_user_text("do the flaky thing")

    assert turn.status == TurnStatus.FAILED
    assert "went wrong" in turn.final_response


@pytest.mark.asyncio
async def test_orchestrator_requires_confirmation_for_high_risk_tool(tmp_settings):
    registry = ToolRegistry()
    registry.register(HighRiskTool())
    provider = ToolCallProvider(tmp_settings.llm, "send_email")

    async def deny(prompt: str) -> str:
        return "no"

    orch = _make_orchestrator(
        tmp_settings, provider, registry, confirmation_manager=ConfirmationManager(ask_fn=deny)
    )

    turn = await orch.handle_user_text("email my boss")

    assert turn.final_response == "Okay, I won't do that."


@pytest.mark.asyncio
async def test_orchestrator_high_risk_tool_without_confirmation_channel_blocks(tmp_settings):
    registry = ToolRegistry()
    registry.register(HighRiskTool())
    provider = ToolCallProvider(tmp_settings.llm, "send_email")
    orch = _make_orchestrator(tmp_settings, provider, registry, confirmation_manager=None)

    turn = await orch.handle_user_text("email my boss")

    assert turn.status == TurnStatus.FAILED
    assert "confirmation" in turn.final_response.lower()


@pytest.mark.asyncio
async def test_orchestrator_missing_required_argument_fails_validation(tmp_settings):
    from app.tools.base import ToolParameter

    class NeedsArgTool(Tool):
        name = "needs_arg"
        description = "test"
        permission_level = PermissionLevel.LOW
        parameters = [ToolParameter(name="query", type="string", description="q")]

        async def execute(self, arguments):
            return ToolResult.ok(message="ok")

    registry = ToolRegistry()
    registry.register(NeedsArgTool())
    provider = ToolCallProvider(tmp_settings.llm, "needs_arg", arguments={})
    orch = _make_orchestrator(tmp_settings, provider, registry)

    turn = await orch.handle_user_text("do the thing")

    assert turn.status == TurnStatus.FAILED
    assert "couldn't do that" in turn.final_response
