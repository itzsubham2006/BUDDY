"""
Jarvis entry point.

V1 status (see README.md "Roadmap" for the full phase breakdown):
    Wired and working:
        - configuration, logging
        - LLM abstraction + orchestrator + tool registry
        - core LOW/MEDIUM tools (apps, files, system, browser, YouTube)
        - permission system + confirmation flow
        - short-term and long-term memory
        - text-to-speech (console fallback if no TTS backend installed)
    Not yet wired into this loop (interfaces exist, implementation is a
    later phase per the project roadmap):
        - wake word / microphone / speech-to-text (Phase 5-6)
        - system tray (Phase 7)
        - Windows autostart (Phase 8)

Until voice is wired up, this runs as a text console loop so the full
LLM -> orchestrator -> tool -> response pipeline can be exercised and
tested end-to-end today.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from app.agent.orchestrator import AgentOrchestrator
from app.browser.playwright_manager import BrowserManager
from app.config import get_settings
from app.llm.client import LLMClient
from app.logging_config import configure_logging
from app.memory.long_term import LongTermMemory
from app.memory.short_term import ShortTermMemory
from app.security.confirmations import ConfirmationManager
from app.security.permissions import PermissionChecker
from app.speech.tts import create_tts
from app.tools.applications import OpenApplicationTool
from app.tools.browser import OpenBrowserTool, SearchWebTool
from app.tools.files import OpenFileTool, OpenFolderTool
from app.tools.registry import ToolRegistry
from app.tools.system import (
    GetCurrentTimeTool,
    GetSystemInfoTool,
    MuteTool,
    UnmuteTool,
    VolumeDownTool,
    VolumeUpTool,
)
from app.tools.youtube import PlayYouTubeTool, SearchYouTubeTool

logger = logging.getLogger("jarvis.main")


def build_tool_registry(browser: BrowserManager, settings) -> ToolRegistry:  # type: ignore[no-untyped-def]
    registry = ToolRegistry()
    registry.register_all(
        [
            OpenApplicationTool(settings.applications),
            OpenFileTool(),
            OpenFolderTool(),
            GetCurrentTimeTool(),
            GetSystemInfoTool(),
            VolumeUpTool(),
            VolumeDownTool(),
            MuteTool(),
            UnmuteTool(),
            OpenBrowserTool(browser),
            SearchWebTool(browser),
            SearchYouTubeTool(browser),
            PlayYouTubeTool(browser),
        ]
    )
    return registry


async def _console_confirmation_ask(prompt: str) -> str:
    """Fallback confirmation channel: ask on stdin. Replaced by
    voice-based confirmation once STT/TTS are fully wired (Phase 5-6)."""
    print(f"🔊 Jarvis: {prompt}")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, "You (yes/no): ")


async def run_console_loop() -> None:
    settings = get_settings()
    configure_logging(settings)
    logger.info("Starting %s (console mode)", settings.agent_name)

    tts = create_tts(settings.speech.tts_provider)
    browser = BrowserManager(engine=settings.browser_engine, headless=settings.browser_headless)
    registry = build_tool_registry(browser, settings)

    permission_checker = PermissionChecker(
        overrides=settings.permission_overrides,
        require_confirmation_high=settings.require_confirmation_high,
        require_confirmation_critical=settings.require_confirmation_critical,
    )
    confirmation_manager = ConfirmationManager(ask_fn=_console_confirmation_ask)

    short_term = ShortTermMemory(max_messages=settings.max_history_messages)
    long_term = LongTermMemory(store_path=settings.memory_long_term_store_path)

    try:
        llm_client = LLMClient(settings.llm)
    except Exception as exc:
        logger.error("Failed to initialize LLM client: %s", exc)
        print(
            f"Could not start the LLM client ({exc}).\n"
            "Check LLM_PROVIDER / LLM_API_KEY in your .env file. "
            "Falling back to offline echo mode for this session."
        )
        from app.llm.client import EchoProvider

        llm_client = LLMClient(settings.llm, provider=EchoProvider(settings.llm))

    orchestrator = AgentOrchestrator(
        llm_client=llm_client,
        tool_registry=registry,
        permission_checker=permission_checker,
        short_term_memory=short_term,
        long_term_memory=long_term,
        confirmation_manager=confirmation_manager,
        agent_name=settings.agent_name,
    )

    print(f"{settings.agent_name} is ready. Type a command (or 'exit' to quit).")
    await tts.speak(f"{settings.agent_name} is ready.")

    try:
        while True:
            loop = asyncio.get_event_loop()
            user_text = await loop.run_in_executor(None, input, "You: ")
            if user_text.strip().lower() in {"exit", "quit"}:
                break
            if not user_text.strip():
                continue

            turn = await orchestrator.handle_user_text(user_text)
            response_text = turn.final_response or "..."
            await tts.speak(response_text)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        await browser.close()
        logger.info("%s shutting down", settings.agent_name)


def main() -> int:
    try:
        asyncio.run(run_console_loop())
    except Exception:  # noqa: BLE001 - top-level safety net
        logger.exception("Fatal error in main loop")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
