"""
Windows "start with Windows" integration.

Uses the current user's Run registry key
(HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run),
which does not require administrator rights and is the standard
mechanism for a per-user autostart entry. This intentionally avoids
Scheduled Tasks / Services, which need elevation.
"""

from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path

logger = logging.getLogger("jarvis.desktop.startup")

_RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "JarvisAssistant"


class StartupError(Exception):
    """Raised when reading/writing the startup registration fails."""


def _require_windows() -> None:
    if platform.system() != "Windows":
        raise StartupError("Startup registration is only supported on Windows.")


def _target_command(executable_path: Path) -> str:
    # Quote in case the install path contains spaces.
    return f'"{executable_path}"'


def enable_startup(executable_path: Path) -> None:
    """Register `executable_path` to launch automatically at user logon."""
    _require_windows()
    import winreg  # type: ignore

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(
                key, _VALUE_NAME, 0, winreg.REG_SZ, _target_command(executable_path)
            )
        logger.info("Startup enabled: %s", executable_path)
    except OSError as exc:
        raise StartupError(f"Failed to enable startup: {exc}") from exc


def disable_startup() -> None:
    """Remove the autostart registration, if present."""
    _require_windows()
    import winreg  # type: ignore

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            try:
                winreg.DeleteValue(key, _VALUE_NAME)
                logger.info("Startup disabled")
            except FileNotFoundError:
                logger.debug("Startup entry did not exist; nothing to remove")
    except OSError as exc:
        raise StartupError(f"Failed to disable startup: {exc}") from exc


def is_startup_enabled() -> bool:
    """Return True if the autostart registry entry currently exists."""
    _require_windows()
    import winreg  # type: ignore

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0, winreg.KEY_READ
        ) as key:
            try:
                winreg.QueryValueEx(key, _VALUE_NAME)
                return True
            except FileNotFoundError:
                return False
    except OSError as exc:
        raise StartupError(f"Failed to read startup state: {exc}") from exc


def default_executable_path() -> Path:
    """Best-guess path to the packaged Jarvis executable, for installers."""
    return Path(sys.executable).resolve()
