"""YouTube tools: search_youtube, play_youtube."""

from __future__ import annotations

from typing import Any

from app.browser.playwright_manager import BrowserError, BrowserManager
from app.security.permissions import PermissionLevel
from app.tools.base import Tool, ToolParameter, ToolResult


class SearchYouTubeTool(Tool):
    name = "search_youtube"
    description = "Search YouTube for a query and open the results page."
    permission_level = PermissionLevel.LOW
    parameters = [
        ToolParameter(name="query", type="string", description="What to search for on YouTube.")
    ]

    def __init__(self, browser: BrowserManager) -> None:
        self._browser = browser

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        query = str(arguments["query"]).strip()
        if not query:
            return ToolResult.fail(error="empty_query", message="I need something to search for.")
        try:
            url = await self._browser.search_youtube(query)
        except BrowserError as exc:
            return ToolResult.fail(error=str(exc), message="I couldn't search YouTube.")
        return ToolResult.ok(message=f"Searching YouTube for {query}.", url=url)


class PlayYouTubeTool(Tool):
    name = "play_youtube"
    description = (
        "Search YouTube for a query and play the first result. "
        "Use this when the user wants something played, not just searched."
    )
    permission_level = PermissionLevel.LOW
    parameters = [
        ToolParameter(name="query", type="string", description="What to search for and play.")
    ]

    def __init__(self, browser: BrowserManager) -> None:
        self._browser = browser

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        query = str(arguments["query"]).strip()
        if not query:
            return ToolResult.fail(error="empty_query", message="I need something to play.")
        try:
            await self._browser.search_youtube(query)
            played = await self._browser.play_first_youtube_result()
        except BrowserError as exc:
            return ToolResult.fail(error=str(exc), message="I couldn't play that on YouTube.")

        if not played:
            return ToolResult.fail(
                error="playback_click_failed",
                message=f"I found results for {query} but couldn't start playback automatically.",
            )
        return ToolResult.ok(message=f"Playing {query} on YouTube.")
