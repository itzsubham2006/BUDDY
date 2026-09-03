"""Browser tools: open_browser, search_web."""

from __future__ import annotations

from typing import Any

from app.browser.playwright_manager import BrowserError, BrowserManager
from app.security.permissions import PermissionLevel
from app.tools.base import Tool, ToolParameter, ToolResult


class OpenBrowserTool(Tool):
    name = "open_browser"
    description = "Open the browser, optionally navigating to a specific URL."
    permission_level = PermissionLevel.LOW
    parameters = [
        ToolParameter(
            name="url",
            type="string",
            description="URL to open. Defaults to a blank/new tab if omitted.",
            required=False,
        )
    ]

    def __init__(self, browser: BrowserManager) -> None:
        self._browser = browser

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        url = arguments.get("url") or "https://www.google.com"
        try:
            await self._browser.goto(url)
        except BrowserError as exc:
            return ToolResult.fail(error=str(exc), message="I couldn't open the browser.")
        return ToolResult.ok(message="Opening the browser.", url=url)


class SearchWebTool(Tool):
    name = "search_web"
    description = "Search the web (Google) for a query and open the results."
    permission_level = PermissionLevel.LOW
    parameters = [
        ToolParameter(name="query", type="string", description="What to search for.")
    ]

    def __init__(self, browser: BrowserManager) -> None:
        self._browser = browser

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        query = str(arguments["query"]).strip()
        if not query:
            return ToolResult.fail(error="empty_query", message="I need something to search for.")
        try:
            url = await self._browser.search_google(query)
        except BrowserError as exc:
            return ToolResult.fail(error=str(exc), message="I couldn't search the web.")
        return ToolResult.ok(message=f"Searching for {query}.", url=url)
