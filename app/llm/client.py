"""
LLM abstraction layer.

The rest of the application talks to `LLMClient`, never to a specific
provider SDK directly. This keeps the agent provider-agnostic: swapping
Anthropic for OpenAI or a local model means writing one new
`LLMProvider` subclass, not touching the orchestrator.
"""

from __future__ import annotations

import abc
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


class EchoProvider(LLMProvider):
    """
    Trivial offline provider used for tests and as a safe default when no
    API key is configured yet. Never calls the network.
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
    "echo": EchoProvider,
}


def register_provider(name: str, provider_cls: type[LLMProvider]) -> None:
    """Allow new providers (openai, azure_openai, ollama, ...) to be plugged in."""
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
            provider_cls = _PROVIDERS.get(config.provider)
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
