"""
Buddy entry point.

Runs either:
1. Hands-free voice assistant mode (`--voice`):
   Microphone -> Wake Word ("Hi Buddy") -> Speech-to-Text -> Orchestrator -> Text-to-Speech
2. Interactive text console mode (default in terminal):
   Keyboard -> Orchestrator -> Tools -> TTS & Screen
"""

from __future__ import annotations

import os
import sys

# Prevent Intel Fortran (ctranslate2/faster-whisper) from aborting on console/window close
os.environ["FOR_DISABLE_CONSOLE_CTRL_HANDLER"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import argparse
import asyncio
import logging
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# When running under pythonw.exe or Windows cp1252 console, ensure safe utf-8 / errors handling
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
elif hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
elif hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.agent.orchestrator import AgentOrchestrator
from app.audio.microphone import NullMicrophone, create_microphone
from app.audio.recorder import RecorderError, create_recorder
from app.audio.wake_word import create_wake_word_detector
from app.browser.playwright_manager import BrowserManager
from app.config import get_settings
from app.desktop.startup import disable_startup, enable_startup, is_startup_enabled
from app.llm.client import LLMClient
from app.logging_config import configure_logging
from app.memory.long_term import LongTermMemory
from app.memory.short_term import ShortTermMemory
from app.security.confirmations import ConfirmationManager
from app.security.permissions import PermissionChecker
from app.speech.stt import create_stt
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

logger = logging.getLogger("buddy.main")


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
    """Fallback confirmation channel on stdin."""
    print(f"[Buddy]: {prompt}")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, "You (yes/no): ")


def _create_llm_client(settings) -> LLMClient:  # type: ignore[no-untyped-def]
    provider_name = (settings.llm.provider or "local").lower()
    if provider_name in ("local", "offline"):
        from app.llm.client import LocalProvider

        print("[Notice] Running in local mode (API-key-free). Basic computer-control commands are active.")
        return LLMClient(settings.llm, provider=LocalProvider(settings.llm))

    if not settings.llm.api_key:
        from app.llm.client import LocalProvider

        print("[Notice] No LLM_API_KEY provided. Running in local mode (basic computer-control commands active).")
        return LLMClient(settings.llm, provider=LocalProvider(settings.llm))

    try:
        client = LLMClient(settings.llm)
        print(f"[LLM] Connected to provider '{settings.llm.provider}' ({settings.llm.model}).")
        return client
    except Exception as exc:
        logger.error("Failed to initialize LLM client: %s", exc)
        print(
            f"Could not start the {settings.llm.provider} client ({exc}).\n"
            "Falling back to local offline mode (basic computer-control commands remain active)."
        )
        from app.llm.client import LocalProvider

        return LLMClient(settings.llm, provider=LocalProvider(settings.llm))


async def run_voice_loop() -> None:
    """Always-listening voice loop: listens for 'Hi Buddy', records command, and responds."""
    settings = get_settings()
    configure_logging(settings)
    logger.info("Starting %s in voice mode", settings.agent_name)

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
    llm_client = _create_llm_client(settings)

    orchestrator = AgentOrchestrator(
        llm_client=llm_client,
        tool_registry=registry,
        permission_checker=permission_checker,
        short_term_memory=short_term,
        long_term_memory=long_term,
        confirmation_manager=confirmation_manager,
        agent_name=settings.agent_name,
    )

    microphone = create_microphone()
    if isinstance(microphone, NullMicrophone):
        msg = "No working microphone found. Please check your audio input devices."
        print(f"[Warning] {msg}")
        await tts.speak(msg)
        return

    stt = create_stt(settings.speech.stt_provider)
    recorder = create_recorder(microphone)
    wake_detector = create_wake_word_detector(
        wake_word=settings.wake_word, microphone=microphone, stt=stt
    )

    ready_msg = f"{settings.agent_name} is online. Say '{settings.wake_word}' to give a command."
    print(f"\n[Ready] {ready_msg}\n")
    await tts.speak(ready_msg)

    try:
        while True:
            try:
                await wake_detector.wait_for_wake_word()
            except Exception as exc:
                logger.error("Wake word error: %s", exc)
                await asyncio.sleep(1)
                continue

            print(f"[Heard] {settings.agent_name} heard wake word! Listening for your command...")
            await tts.speak("Yes?")

            try:
                wav_bytes = await recorder.record_utterance(timeout_seconds=8.0)
                user_text = await stt.transcribe(wav_bytes)
            except RecorderError:
                print("[Timeout] No speech detected.")
                continue
            except Exception as exc:
                logger.warning("Recording/transcription failed: %s", exc)
                continue

            if not user_text.strip():
                continue

            print(f"\n[You]: {user_text}")
            turn = await orchestrator.handle_user_text(user_text)
            response_text = turn.final_response or "Done."
            print(f"[{settings.agent_name}]: {response_text}\n")
            await tts.speak(response_text)

    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        wake_detector.stop()
        await browser.close()
        logger.info("%s voice loop ended.", settings.agent_name)


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
    llm_client = _create_llm_client(settings)

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
    print("Tip: Run with `python -m app.main --voice` for hands-free voice mode!\n")
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
    parser = argparse.ArgumentParser(description="Buddy Personal Assistant")
    parser.add_argument("--voice", action="store_true", help="Run hands-free voice assistant mode")
    parser.add_argument("--console", action="store_true", help="Run in interactive console mode")
    parser.add_argument("--enable-startup", action="store_true", help="Enable auto-start when Windows turns on")
    parser.add_argument("--disable-startup", action="store_true", help="Disable Windows auto-start")
    parser.add_argument("--status-startup", action="store_true", help="Check Windows auto-start status")

    args, _ = parser.parse_known_args()

    if args.enable_startup:
        cmd = enable_startup()
        print(f"[OK] Buddy auto-start enabled: {cmd}")
        return 0

    if args.disable_startup:
        disable_startup()
        print("[OK] Buddy auto-start disabled.")
        return 0

    if args.status_startup:
        enabled = is_startup_enabled()
        print(f"Buddy auto-start: {'ENABLED' if enabled else 'DISABLED'}")
        return 0

    # If --voice or if running without a tty / in background, run voice loop
    is_headless_or_background = not sys.stdin or not sys.stdin.isatty()
    run_voice = args.voice or (is_headless_or_background and not args.console)

    try:
        if run_voice:
            asyncio.run(run_voice_loop())
        else:
            asyncio.run(run_console_loop())
    except Exception:  # noqa: BLE001
        logger.exception("Fatal error in main loop")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
