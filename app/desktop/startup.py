"""
Windows "start with Windows" integration.

Uses the current user's Run registry key
(HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run),
which does not require administrator rights and is the standard
mechanism for a per-user autostart entry.
"""

from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("buddy.desktop.startup")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "BuddyAssistant"


class StartupError(Exception):
    """Raised when reading/writing the startup registration fails."""


def _require_windows() -> None:
    if platform.system() != "Windows":
        raise StartupError("Startup registration is only supported on Windows.")


def build_startup_command(python_exe: Optional[Path] = None, headless: bool = True) -> str:
    """Build the command line string to run Buddy on startup."""
    exe = python_exe or Path(sys.executable).resolve()

    # If running with python.exe in a venv, prefer pythonw.exe to run without a black console window
    if headless and exe.name.lower() == "python.exe":
        pythonw = exe.parent / "pythonw.exe"
        if pythonw.exists():
            exe = pythonw

    main_script = PROJECT_ROOT / "app" / "main.py"
    return f'"{exe}" "{main_script}" --voice'


def enable_startup(executable_path: Optional[Path] = None, command: Optional[str] = None) -> str:
    """Register Buddy to launch automatically at user logon."""
    _require_windows()
    import winreg  # type: ignore

    cmd = command or (f'"{executable_path}"' if executable_path else build_startup_command())

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(
                key, _VALUE_NAME, 0, winreg.REG_SZ, cmd
            )
        logger.info("Startup enabled for Buddy: %s", cmd)
        return cmd
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
                logger.info("Startup disabled for Buddy")
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
    """Best-guess path to the packaged Buddy executable, for installers."""
    return Path(sys.executable).resolve()
