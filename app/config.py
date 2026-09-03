"""
Centralized configuration for Jarvis.

Design principles
------------------
* Secrets (API keys) come ONLY from environment variables / `.env`.
* Non-secret settings (app paths, wake word, timeouts) come from a YAML file.
* Nothing in this module ever logs a secret value.
* A single `Settings` object is constructed once and passed around
  explicitly (no hidden global mutable state beyond a lazily-created
  singleton accessor, `get_settings()`, which is safe because settings
  are read-only after load).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(Exception):
    """Raised when configuration cannot be loaded or is invalid."""


@dataclass(frozen=True)
class ApplicationEntry:
    """Launch configuration for a single desktop application."""

    key: str
    display_name: str
    executable: Optional[str] = None
    fallback_executables: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: Optional[str]


@dataclass(frozen=True)
class SpeechConfig:
    stt_provider: str
    stt_api_key: Optional[str]
    tts_provider: str
    tts_api_key: Optional[str]


@dataclass(frozen=True)
class Settings:
    """Fully resolved application settings."""

    # Secrets / environment-driven
    llm: LLMConfig
    speech: SpeechConfig
    wake_word: str
    porcupine_access_key: Optional[str]
    log_level: str
    data_dir: Path
    require_confirmation: bool

    # YAML-driven
    agent_name: str
    max_history_messages: int
    listen_timeout_seconds: int
    applications: dict[str, ApplicationEntry]
    browser_headless: bool
    browser_engine: str
    default_search_engine: str
    permission_overrides: dict[str, str]
    require_confirmation_high: bool
    require_confirmation_critical: bool
    memory_short_term_max_messages: int
    memory_long_term_store_path: Path
    log_dir: Path
    log_max_bytes: int
    log_backup_count: int

    raw_yaml: dict[str, Any] = field(default_factory=dict, repr=False)


def _load_yaml(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        # Fall back to the example so the app is runnable out of the box.
        example = PROJECT_ROOT / "config" / "config.example.yaml"
        if example.exists():
            config_path = example
        else:
            raise ConfigError(
                f"No config file found at {config_path} and no example config "
                "available."
            )
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def _expand(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return os.path.expandvars(value)


def load_settings(
    env_file: Optional[Path] = None,
    config_file: Optional[Path] = None,
) -> Settings:
    """Load settings from `.env` and `config.yaml`.

    Parameters
    ----------
    env_file:
        Optional explicit path to a .env file. Defaults to `<project_root>/.env`.
    config_file:
        Optional explicit path to config.yaml. Defaults to the value of the
        CONFIG_FILE env var, or `<project_root>/config/config.yaml`.
    """
    load_dotenv(dotenv_path=env_file or (PROJECT_ROOT / ".env"), override=False)

    config_path = config_file or Path(
        os.environ.get("CONFIG_FILE", PROJECT_ROOT / "config" / "config.yaml")
    )
    yaml_data = _load_yaml(config_path)

    agent_cfg = yaml_data.get("agent", {})
    apps_cfg = yaml_data.get("applications", {})
    browser_cfg = yaml_data.get("browser", {})
    perms_cfg = yaml_data.get("permissions", {})
    memory_cfg = yaml_data.get("memory", {})
    logging_cfg = yaml_data.get("logging", {})

    applications: dict[str, ApplicationEntry] = {}
    for key, entry in apps_cfg.items():
        applications[key] = ApplicationEntry(
            key=key,
            display_name=entry.get("display_name", key.title()),
            executable=_expand(entry.get("executable")),
            fallback_executables=tuple(
                _expand(p) for p in entry.get("fallback_executables", [])
            ),
        )

    data_dir = Path(os.environ.get("DATA_DIR", PROJECT_ROOT / "data"))

    settings = Settings(
        llm=LLMConfig(
            provider=os.environ.get("LLM_PROVIDER", "anthropic"),
            model=os.environ.get("LLM_MODEL", "claude-sonnet-4-6"),
            api_key=os.environ.get("LLM_API_KEY") or None,
        ),
        speech=SpeechConfig(
            stt_provider=os.environ.get("STT_PROVIDER", "whisper_local"),
            stt_api_key=os.environ.get("STT_API_KEY") or None,
            tts_provider=os.environ.get("TTS_PROVIDER", "pyttsx3"),
            tts_api_key=os.environ.get("TTS_API_KEY") or None,
        ),
        wake_word=os.environ.get("WAKE_WORD", agent_cfg.get("wake_word", "Hi Buddy")),
        porcupine_access_key=os.environ.get("PORCUPINE_ACCESS_KEY") or None,
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        data_dir=data_dir,
        require_confirmation=os.environ.get("REQUIRE_CONFIRMATION", "true").lower()
        in ("1", "true", "yes"),
        agent_name=os.environ.get("AGENT_NAME", agent_cfg.get("name", "Buddy")),
        max_history_messages=int(agent_cfg.get("max_history_messages", 20)),
        listen_timeout_seconds=int(agent_cfg.get("listen_timeout_seconds", 6)),
        applications=applications,
        browser_headless=bool(browser_cfg.get("headless", False)),
        browser_engine=browser_cfg.get("default_engine", "chromium"),
        default_search_engine=browser_cfg.get("default_search_engine", "google"),
        permission_overrides=perms_cfg.get("overrides", {}) or {},
        require_confirmation_high=bool(perms_cfg.get("require_confirmation_high", True)),
        require_confirmation_critical=bool(
            perms_cfg.get("require_confirmation_critical", True)
        ),
        memory_short_term_max_messages=int(
            memory_cfg.get("short_term_max_messages", 20)
        ),
        memory_long_term_store_path=Path(
            memory_cfg.get("long_term_store_path", data_dir / "memory" / "long_term.json")
        ),
        log_dir=Path(logging_cfg.get("log_dir", data_dir / "logs")),
        log_max_bytes=int(logging_cfg.get("max_bytes", 1_048_576)),
        log_backup_count=int(logging_cfg.get("backup_count", 5)),
        raw_yaml=yaml_data,
    )
    return settings


_settings_singleton: Optional[Settings] = None


def get_settings(force_reload: bool = False) -> Settings:
    """Return a process-wide cached Settings instance."""
    global _settings_singleton
    if _settings_singleton is None or force_reload:
        _settings_singleton = load_settings()
    return _settings_singleton
