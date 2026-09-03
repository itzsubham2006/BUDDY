from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ApplicationEntry, LLMConfig, SpeechConfig, Settings  # noqa: E402


@pytest.fixture
def tmp_settings(tmp_path) -> Settings:
    """A minimal, fully-isolated Settings instance for tests (no real files/network)."""
    return Settings(
        llm=LLMConfig(provider="echo", model="test-model", api_key=None),
        speech=SpeechConfig(
            stt_provider="whisper_local", stt_api_key=None, tts_provider="console", tts_api_key=None
        ),
        wake_word="Hey Jarvis",
        porcupine_access_key=None,
        log_level="INFO",
        data_dir=tmp_path / "data",
        require_confirmation=True,
        agent_name="Jarvis",
        max_history_messages=20,
        listen_timeout_seconds=6,
        applications={
            "notepad": ApplicationEntry(key="notepad", display_name="Notepad", executable="notepad")
        },
        browser_headless=True,
        browser_engine="chromium",
        default_search_engine="google",
        permission_overrides={},
        require_confirmation_high=True,
        require_confirmation_critical=True,
        memory_short_term_max_messages=20,
        memory_long_term_store_path=tmp_path / "data" / "memory" / "long_term.json",
        log_dir=tmp_path / "data" / "logs",
        log_max_bytes=1_048_576,
        log_backup_count=5,
        raw_yaml={},
    )
