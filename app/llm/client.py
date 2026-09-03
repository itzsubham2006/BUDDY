"""
LLM abstraction layer.

The rest of the application talks to `LLMClient`, never to a specific
provider SDK directly. This keeps the agent provider-agnostic: swapping
Anthropic for OpenAI, OpenRouter, or a completely local/offline model
means writing one new `LLMProvider` subclass, not touching the orchestrator.
"""

from __future__ import annotations

import abc
import json
import logging
from typing import Any, Optional

from app.config import LLMConfig
from app.llm.models import LLMResponse, Message

logger = logging.getLogger("jarvis.llm")


class LLMError(Exception):
    """Raised when the LLM provider fails (network, auth, timeout, etc.)."""


class LLMProvider(abc.ABC):
    """Interface every concrete LLM backend must implement."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abc.abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Send a chat completion request, optionally with tool schemas."""
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    """Provider backed by the Anthropic Messages API."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        if not config.api_key:
            raise LLMError(
                "LLM_API_KEY is not set. Add it to your .env file (never commit it)."
            )
        try:
            import anthropic  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise LLMError(
                "The 'anthropic' package is required for LLM_PROVIDER=anthropic. "
                "Install it with `pip install anthropic`."
            ) from exc
        self._client = anthropic.AsyncAnthropic(api_key=config.api_key)

    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        from app.llm.models import ToolCall  # local import avoids cycle

        api_messages = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": 1024,
            "messages": api_messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = tools

        try:
            response = await self._client.messages.create(**kwargs)
        except Exception as exc:  # broad: network/auth/timeout all normalized here
            logger.error("Anthropic API call failed: %s", exc.__class__.__name__)
            raise LLMError(f"LLM request failed: {exc.__class__.__name__}") from exc

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(name=block.name, arguments=dict(block.input), call_id=block.id)
                )

        return LLMResponse(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            raw=response,
        )


class OpenAIProvider(LLMProvider):
    """Provider backed by OpenAI or any OpenAI-compatible API."""

    def __init__(
        self,
        config: LLMConfig,
        base_url: Optional[str] = None,
        default_headers: Optional[dict[str, str]] = None,
    ) -> None:
        super().__init__(config)
        if not config.api_key:
            raise LLMError(
                "LLM_API_KEY is not set. Add it to your .env file (never commit it)."
            )
        try:
            import openai  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise LLMError(
                "The 'openai' package is required for OpenAI/OpenRouter providers. "
                "Install it with `pip install openai`."
            ) from exc

        self._client = openai.AsyncOpenAI(
            api_key=config.api_key,
            base_url=base_url,
            default_headers=default_headers,
        )

    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        from app.llm.models import ToolCall

        api_messages: list[dict[str, Any]] = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        for m in messages:
            if m.role == "system" and not system_prompt:
                api_messages.append({"role": "system", "content": m.content})
            elif m.role != "system":
                api_messages.append({"role": m.role, "content": m.content})

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": api_messages,
        }

        if tools:
            formatted_tools = []
            for t in tools:
                # Convert input_schema if present
                parameters = t.get("input_schema") or {
                    "type": "object",
                    "properties": t.get("properties", {}),
                    "required": t.get("required", []),
                }
                formatted_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "description": t.get("description", ""),
                            "parameters": parameters,
                        },
                    }
                )
            kwargs["tools"] = formatted_tools

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            logger.error("OpenAI/OpenRouter API call failed: %s", exc)
            raise LLMError(f"LLM request failed: {exc.__class__.__name__} ({exc})") from exc

        choice = response.choices[0]
        msg = choice.message
        text = msg.content or None
        tool_calls: list[ToolCall] = []

        if msg.tool_calls:
            for tc in msg.tool_calls:
                raw_args = tc.function.arguments
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except Exception:
                        args = {}
                elif isinstance(raw_args, dict):
                    args = raw_args
                else:
                    args = {}
                tool_calls.append(
                    ToolCall(name=tc.function.name, arguments=args, call_id=tc.id)
                )

        return LLMResponse(text=text, tool_calls=tool_calls, raw=response)


class OpenRouterProvider(OpenAIProvider):
    """Provider backed by OpenRouter (OpenAI-compatible endpoint)."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(
            config=config,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/itzsubham2006/BUDDY",
                "X-Title": "Jarvis Desktop Agent",
            },
        )


class LocalProvider(LLMProvider):
    """
    Completely local, offline command dispatcher that requires 0 cloud API keys.
    Interprets basic computer-control commands (apps, volume, time, system info,
    web & YouTube search) via deterministic matching and converts them to ToolCall instances.
    """

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        from app.agent.local_matcher import LocalCommandMatcher

        self._matcher = LocalCommandMatcher()

    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        matched_tool = self._matcher.match(last_user)
        if matched_tool:
            return LLMResponse(text=None, tool_calls=[matched_tool])

        return LLMResponse(
            text=(
                "I am running in local offline mode without a cloud LLM. "
                "I can execute desktop commands like 'open chrome', 'notepad', 'calc', "
                "'volume up', 'volume down', 'mute', 'unmute', 'what time is it', "
                "'system info', 'search web for ...', and 'search youtube for ...'."
            )
        )


class EchoProvider(LLMProvider):
    """
    Trivial offline provider used for tests and as a safe fallback.
    Never calls the network.
    """

    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return LLMResponse(text=f"(offline echo) You said: {last_user}")


_PROVIDERS: dict[str, type[LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
    "local": LocalProvider,
    "offline": LocalProvider,
    "echo": EchoProvider,
}


def register_provider(name: str, provider_cls: type[LLMProvider]) -> None:
    """Allow new providers (azure_openai, ollama, ...) to be plugged in."""
    _PROVIDERS[name] = provider_cls


class LLMClient:
    """
    Public-facing client used by the rest of the app.

    Wraps a concrete `LLMProvider` chosen by `config.LLM_PROVIDER`, and
    exposes the higher-level operations the orchestrator needs.
    """

    def __init__(self, config: LLMConfig, provider: Optional[LLMProvider] = None) -> None:
        self.config = config
        if provider is not None:
            self._provider = provider
        else:
            provider_cls = _PROVIDERS.get(config.provider.lower())
            if provider_cls is None:
                raise LLMError(
                    f"Unknown LLM_PROVIDER '{config.provider}'. "
                    f"Available: {list(_PROVIDERS)}"
                )
            self._provider = provider_cls(config)

    async def chat(
        self,
        messages: list[Message],
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Plain conversational turn, no tool use."""
        return await self._provider.chat(messages, tools=None, system_prompt=system_prompt)

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Single-shot text generation convenience wrapper."""
        response = await self._provider.chat(
            [Message(role="user", content=prompt)], system_prompt=system_prompt
        )
        return response.text or ""

    async def choose_tool(
        self,
        messages: list[Message],
        tool_schemas: list[dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Ask the LLM to pick a tool (or respond directly) given the schemas."""
        return await self._provider.chat(
            messages, tools=tool_schemas, system_prompt=system_prompt
        )
