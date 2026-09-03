from __future__ import annotations

import pytest

from app.security.confirmations import ConfirmationManager, ConfirmationRequest


@pytest.mark.asyncio
async def test_confirmed_on_yes():
    async def ask(prompt: str) -> str:
        return "yes"

    manager = ConfirmationManager(ask_fn=ask)
    result = await manager.request_confirmation(
        ConfirmationRequest(tool_name="t", summary="Doing thing.", arguments={})
    )
    assert result.confirmed is True


@pytest.mark.asyncio
async def test_denied_on_no():
    async def ask(prompt: str) -> str:
        return "no"

    manager = ConfirmationManager(ask_fn=ask)
    result = await manager.request_confirmation(
        ConfirmationRequest(tool_name="t", summary="Doing thing.", arguments={})
    )
    assert result.confirmed is False


@pytest.mark.asyncio
async def test_ambiguous_defaults_to_denied():
    async def ask(prompt: str) -> str:
        return "maybe later idk"

    manager = ConfirmationManager(ask_fn=ask)
    result = await manager.request_confirmation(
        ConfirmationRequest(tool_name="t", summary="Doing thing.", arguments={})
    )
    assert result.confirmed is False


@pytest.mark.asyncio
async def test_empty_response_denied():
    async def ask(prompt: str) -> str:
        return ""

    manager = ConfirmationManager(ask_fn=ask)
    result = await manager.request_confirmation(
        ConfirmationRequest(tool_name="t", summary="Doing thing.", arguments={})
    )
    assert result.confirmed is False
