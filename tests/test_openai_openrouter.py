from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import LLMConfig
from app.llm.client import LLMClient, OpenAIProvider, OpenRouterProvider
from app.llm.models import Message


def test_openrouter_provider_configuration():
    cfg = LLMConfig(
        provider="openrouter",
        model="nvidia/nemotron-3.5-lightning",
        api_key="sk-or-v1-test",
    )
    provider = OpenRouterProvider(cfg)
    assert provider.config.provider == "openrouter"
    assert provider._client.base_url == "https://openrouter.ai/api/v1/"
    assert provider._client.api_key == "sk-or-v1-test"


def test_openai_provider_missing_key_raises():
    cfg = LLMConfig(provider="openai", model="gpt-4o-mini", api_key=None)
    with pytest.raises(Exception) as exc_info:
        OpenAIProvider(cfg)
    assert "LLM_API_KEY is not set" in str(exc_info.value)


@pytest.mark.asyncio
async def test_openai_provider_chat_completions():
    cfg = LLMConfig(provider="openai", model="gpt-4o-mini", api_key="sk-test-key")
    provider = OpenAIProvider(cfg)

    # Mock response from openai chat completions
    mock_choice = MagicMock()
    mock_choice.message.content = "Hello there!"
    mock_choice.message.tool_calls = None
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    with patch.object(
        provider._client.chat.completions,
        "create",
        new=AsyncMock(return_value=mock_completion),
    ) as mock_create:
        response = await provider.chat([Message(role="user", content="Hi")])

        assert response.text == "Hello there!"
        assert response.tool_calls == []
        mock_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_openai_provider_tool_calls_formatting():
    cfg = LLMConfig(
        provider="openrouter",
        model="nvidia/nemotron-3.5-lightning",
        api_key="sk-or-v1-test",
    )
    provider = OpenRouterProvider(cfg)

    # Mock tool call in response
    mock_tc = MagicMock()
    mock_tc.id = "call_123"
    mock_tc.function.name = "open_application"
    mock_tc.function.arguments = json.dumps({"application": "chrome"})

    mock_choice = MagicMock()
    mock_choice.message.content = None
    mock_choice.message.tool_calls = [mock_tc]
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    with patch.object(
        provider._client.chat.completions,
        "create",
        new=AsyncMock(return_value=mock_completion),
    ):
        tools = [
            {
                "name": "open_application",
                "description": "Open an app",
                "input_schema": {
                    "type": "object",
                    "properties": {"application": {"type": "string"}},
                    "required": ["application"],
                },
            }
        ]
        response = await provider.chat(
            [Message(role="user", content="open chrome")],
            tools=tools,
            system_prompt="System prompt here",
        )

        assert response.wants_tool_call is True
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "open_application"
        assert response.tool_calls[0].arguments == {"application": "chrome"}
        assert response.tool_calls[0].call_id == "call_123"


def test_llm_client_dispatches_openrouter():
    cfg = LLMConfig(
        provider="openrouter",
        model="nvidia/nemotron-3.5-lightning",
        api_key="sk-or-v1-test",
    )
    client = LLMClient(cfg)
    assert isinstance(client._provider, OpenRouterProvider)
