"""
BrowserManager: a thin, tool-agnostic wrapper around Playwright.

Kept isolated from `app/tools/browser.py` so browser tools stay simple and
the underlying automation engine (Playwright today) could be swapped
later without touching tool code. Uses DOM selectors, never hard-coded
screen coordinates.
"""

from __future__ import annotations

import logging
import urllib.parse
from typing import Optional

logger = logging.getLogger("jarvis.browser")


class BrowserError(Exception):
    """Raised when a browser automation step fails."""


class BrowserManager:
    """
    Lazily starts a single shared Playwright browser/page and exposes
    high-level actions. Safe to call `close()` multiple times.
    """

    def __init__(self, engine: str = "chromium", headless: bool = False) -> None:
        self._engine = engine
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._page = None

    async def _ensure_started(self) -> None:
        if self._page is not None:
            return
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover
            raise BrowserError(
                "The 'playwright' package (and browsers) must be installed. "
                "Run `pip install playwright` then `playwright install chromium`."
            ) from exc

        self._playwright = await async_playwright().start()
        browser_type = getattr(self._playwright, self._engine)
        self._browser = await browser_type.launch(headless=self._headless)
        self._page = await self._browser.new_page()
        logger.info("Browser started (engine=%s, headless=%s)", self._engine, self._headless)

    async def goto(self, url: str) -> None:
        await self._ensure_started()
        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
        except Exception as exc:  # pragma: no cover - network/timeout dependent
            raise BrowserError(f"Failed to navigate to {url}: {exc}") from exc

    async def search_google(self, query: str) -> str:
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
        await self.goto(url)
        return url

    async def search_youtube(self, query: str) -> str:
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
        await self.goto(url)
        return url

    async def play_first_youtube_result(self) -> bool:
        """Click the first video result on a YouTube search results page."""
        await self._ensure_started()
        try:
            selector = "a#video-title"
            await self._page.wait_for_selector(selector, timeout=10000)
            await self._page.click(selector)
            return True
        except Exception as exc:  # pragma: no cover - depends on live page structure
            logger.warning("Could not click first YouTube result: %s", exc)
            return False

    async def read_page_text(self, max_chars: int = 2000) -> str:
        await self._ensure_started()
        try:
            text = await self._page.inner_text("body")
        except Exception as exc:  # pragma: no cover
            raise BrowserError(f"Failed to read page text: {exc}") from exc
        return text[:max_chars]

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        self._page = None
        logger.info("Browser closed")
