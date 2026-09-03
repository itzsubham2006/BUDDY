from __future__ import annotations

import pytest

from app.agent.local_matcher import LocalCommandMatcher
from app.config import LLMConfig
from app.llm.client import LocalProvider
from app.llm.models import Message


def test_local_matcher_volume_controls():
    matcher = LocalCommandMatcher()

    res = matcher.match("volume up")
    assert res is not None
    assert res.name == "volume_up"

    res = matcher.match("turn down the volume")
    assert res is not None
    assert res.name == "volume_down"

    res = matcher.match("mute audio")
    assert res is not None
    assert res.name == "mute"

    res = matcher.match("unmute")
    assert res is not None
    assert res.name == "unmute"


def test_local_matcher_time_and_system():
    matcher = LocalCommandMatcher()

    res = matcher.match("what time is it?")
    assert res is not None
    assert res.name == "get_current_time"

    res = matcher.match("tell me the time")
    assert res is not None
    assert res.name == "get_current_time"

    res = matcher.match("show system info")
    assert res is not None
    assert res.name == "get_system_info"


def test_local_matcher_applications():
    matcher = LocalCommandMatcher()

    res = matcher.match("open chrome")
    assert res is not None
    assert res.name == "open_application"
    assert res.arguments == {"application": "chrome"}

    res = matcher.match("launch VS Code")
    assert res is not None
    assert res.name == "open_application"
    assert res.arguments == {"application": "vscode"}

    res = matcher.match("start notepad")
    assert res is not None
    assert res.name == "open_application"
    assert res.arguments == {"application": "notepad"}

    res = matcher.match("calculator")
    assert res is not None
    assert res.name == "open_application"
    assert res.arguments == {"application": "calculator"}


def test_local_matcher_search_and_media():
    matcher = LocalCommandMatcher()

    res = matcher.match("search web for python tutorials")
    assert res is not None
    assert res.name == "search_web"
    assert res.arguments == {"query": "python tutorials"}

    res = matcher.match("search youtube for lofi hip hop")
    assert res is not None
    assert res.name == "search_youtube"
    assert res.arguments == {"query": "lofi hip hop"}

    res = matcher.match("play mozart on youtube")
    assert res is not None
    assert res.name == "play_youtube"
    assert res.arguments == {"query": "mozart"}


def test_local_matcher_unmatched():
    matcher = LocalCommandMatcher()
    res = matcher.match("write a 500 word essay on philosophy")
    assert res is None


@pytest.mark.asyncio
async def test_local_provider_generates_tool_call():
    cfg = LLMConfig(provider="local", model="offline", api_key=None)
    provider = LocalProvider(cfg)

    response = await provider.chat([Message(role="user", content="open notepad")])
    assert response.wants_tool_call is True
    assert response.tool_calls[0].name == "open_application"
    assert response.tool_calls[0].arguments == {"application": "notepad"}


@pytest.mark.asyncio
async def test_local_provider_unmatched_returns_helpful_message():
    cfg = LLMConfig(provider="local", model="offline", api_key=None)
    provider = LocalProvider(cfg)

    response = await provider.chat([Message(role="user", content="compose a song")])
    assert response.wants_tool_call is False
    assert "local offline mode" in response.text
