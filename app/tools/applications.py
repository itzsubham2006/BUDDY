"""
Windows application launching.

Supports:
1. Explicitly configured application entries from config.yaml.
2. Built-in mapping for all Windows system applications (Settings, Task Manager,
   Control Panel, Paint, Snipping Tool, Terminal, Camera, Clock, Calculator, etc.).
3. Dynamic Start Menu shortcut (.lnk) discovery across user and system directories,
   allowing any installed desktop application (Discord, Steam, VLC, Word, etc.)
   to be launched by name.
4. PATH lookup via `shutil.which` and native Windows shell launch via `os.startfile`.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from app.config import ApplicationEntry
from app.security.permissions import PermissionLevel
from app.tools.base import Tool, ToolParameter, ToolResult

logger = logging.getLogger("jarvis.tools.applications")

# Comprehensive mapping for Windows system tools, utilities, and URI schemes
_SYSTEM_APPS: dict[str, str] = {
    # Browsers
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "firefox": "firefox",
    "mozilla firefox": "firefox",
    "brave": "brave",
    # Dev & Editors
    "vscode": "code",
    "vs code": "code",
    "code": "code",
    "visual studio code": "code",
    "notepad": "notepad",
    "wordpad": "write",
    # Windows System Utilities
    "explorer": "explorer",
    "file explorer": "explorer",
    "files": "explorer",
    "task manager": "taskmgr",
    "taskmanager": "taskmgr",
    "taskmgr": "taskmgr",
    "control panel": "control",
    "control": "control",
    "settings": "ms-settings:",
    "windows settings": "ms-settings:",
    "cmd": "cmd",
    "command prompt": "cmd",
    "powershell": "powershell",
    "terminal": "wt",
    "windows terminal": "wt",
    "device manager": "devmgmt.msc",
    "disk management": "diskmgmt.msc",
    "registry editor": "regedit",
    "regedit": "regedit",
    "services": "services.msc",
    "event viewer": "eventvwr.msc",
    # Built-in Apps & Accessories
    "calculator": "calc",
    "calc": "calc",
    "paint": "mspaint",
    "mspaint": "mspaint",
    "snipping tool": "snippingtool",
    "snip": "snippingtool",
    "camera": "microsoft.windows.camera:",
    "clock": "ms-clock:",
    "alarm": "ms-clock:",
    "alarms": "ms-clock:",
    "calendar": "outlookcal:",
    "weather": "bingweather:",
    "maps": "bingmaps:",
    "store": "ms-windows-store:",
    "microsoft store": "ms-windows-store:",
    "photos": "ms-photos:",
    "spotify": "spotify",
    "media player": "mswindowsmusic:",
}

# Cache for Start Menu shortcuts to avoid filesystem scanning on every query
_START_MENU_CACHE: dict[str, str] = {}
_START_MENU_SCANNED = False


def _index_start_menu() -> dict[str, str]:
    """Scan Windows Start Menu folders for installed .lnk shortcuts."""
    global _START_MENU_CACHE, _START_MENU_SCANNED
    if _START_MENU_SCANNED:
        return _START_MENU_CACHE

    shortcuts: dict[str, str] = {}
    search_dirs = []

    app_data = os.environ.get("APPDATA")
    if app_data:
        search_dirs.append(Path(app_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs")

    prog_data = os.environ.get("ProgramData")
    if prog_data:
        search_dirs.append(Path(prog_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs")

    for base_dir in search_dirs:
        if not base_dir.exists():
            continue
        try:
            for lnk_path in base_dir.rglob("*.lnk"):
                name = lnk_path.stem.lower()
                shortcuts[name] = str(lnk_path)
                # Also index stripped version (e.g. "Google Chrome" -> "chrome")
                if " " in name:
                    for part in name.split():
                        if len(part) > 3 and part not in shortcuts:
                            shortcuts[part] = str(lnk_path)
        except Exception as exc:
            logger.debug("Failed scanning start menu directory %s: %s", base_dir, exc)

    _START_MENU_CACHE = shortcuts
    _START_MENU_SCANNED = True
    return _START_MENU_CACHE


def _resolve_executable(key: str, applications: dict[str, ApplicationEntry]) -> Optional[str]:
    """Resolve an app key into an executable path, command, URI scheme, or .lnk shortcut."""
    cleaned = key.strip().lower()

    # 1. Configured applications in config.yaml
    entry = applications.get(cleaned)
    candidates: list[str] = []
    if entry:
        if entry.executable:
            candidates.append(entry.executable)
        candidates.extend(entry.fallback_executables)

    # 2. Built-in system apps table
    sys_app = _SYSTEM_APPS.get(cleaned)
    if sys_app:
        candidates.append(sys_app)

    # 3. Direct bare name check
    candidates.append(cleaned)

    for candidate in candidates:
        # URI protocols (e.g. ms-settings:, microsoft.windows.camera:)
        if ":" in candidate and not candidate.startswith(("\\", "/", "C:", "c:")):
            return candidate

        # Absolute or relative path that exists
        if os.path.isabs(candidate) and os.path.exists(candidate):
            return candidate

        # Bare command resolvable on PATH
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    # 4. Start Menu shortcuts (.lnk files)
    start_menu = _index_start_menu()
    if cleaned in start_menu:
        return start_menu[cleaned]

    # Partial match in start menu
    for name, path in start_menu.items():
        if cleaned in name or name in cleaned:
            return path

    return None


class OpenApplicationTool(Tool):
    name = "open_application"
    description = (
        "Open any desktop or system application by name, e.g. chrome, edge, notepad, "
        "calculator, settings, task manager, control panel, paint, terminal, spotify, "
        "or any other installed program."
    )
    permission_level = PermissionLevel.LOW
    parameters = [
        ToolParameter(
            name="application",
            type="string",
            description="Application name or key to open.",
            required=True,
        )
    ]

    def __init__(self, applications: Optional[dict[str, ApplicationEntry]] = None) -> None:
        self._applications = applications or {}

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        key = str(arguments.get("application", "")).strip().lower()
        if not key:
            return ToolResult.fail(
                error="missing_application_name",
                message="Please specify an application to open.",
            )

        executable = _resolve_executable(key, self._applications)
        if executable is None:
            return ToolResult.fail(
                error="application_not_found",
                message=f"I couldn't find '{key}' on this computer.",
            )

        if platform.system() != "Windows":
            logger.info(
                "Non-Windows platform detected; simulating launch of '%s' (%s)",
                key,
                executable,
            )
            return ToolResult.ok(
                message=f"(simulated) Opening {key}.",
                executable=executable,
                simulated=True,
            )

        try:
            is_uri = (
                executable.startswith(("ms-", "microsoft."))
                or (":" in executable and not os.path.isabs(executable) and executable[1:3] not in (":\\", ":/"))
            )
            if is_uri or executable.endswith((".lnk", ".msc")):
                os.startfile(executable)  # noqa: S606
            else:
                # Regular executable - launch via subprocess
                subprocess.Popen([executable], shell=False)  # noqa: S603
        except OSError as exc:
            logger.error("Failed to launch '%s' (%s): %s", key, executable, exc)
            return ToolResult.fail(
                error=str(exc), message=f"I found '{key}' but couldn't launch it."
            )

        display_name = (
            self._applications[key].display_name
            if key in self._applications
            else key.title()
        )
        return ToolResult.ok(message=f"Opening {display_name}.", executable=executable)
