"""
Windows application launching.

Application paths come from config (see config/config.example.yaml) rather
than being hard-coded, and `shutil.which` is used as a fallback so common
apps still launch even without explicit configuration. Launching is done
via `subprocess.Popen` with a fixed executable — never through a shell
string built from LLM-provided text — to avoid command-injection risk.
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from typing import Any, Optional

from app.config import ApplicationEntry
from app.security.permissions import PermissionLevel
from app.tools.base import Tool, ToolParameter, ToolResult

logger = logging.getLogger("jarvis.tools.applications")

# Known bare commands to try via PATH lookup if not explicitly configured.
_FALLBACK_COMMANDS: dict[str, str] = {
    "chrome": "chrome",
    "edge": "msedge",
    "firefox": "firefox",
    "vscode": "code",
    "explorer": "explorer",
    "spotify": "spotify",
    "notepad": "notepad",
    "calculator": "calc",
}


def _resolve_executable(key: str, applications: dict[str, ApplicationEntry]) -> Optional[str]:
    entry = applications.get(key)
    candidates: list[str] = []
    if entry:
        if entry.executable:
            candidates.append(entry.executable)
        candidates.extend(entry.fallback_executables)

    fallback_cmd = _FALLBACK_COMMANDS.get(key)
    if fallback_cmd:
        candidates.append(fallback_cmd)

    for candidate in candidates:
        # Absolute/relative path that exists on disk.
        import os

        if os.path.isabs(candidate) and os.path.exists(candidate):
            return candidate
        # Bare command resolvable on PATH.
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


class OpenApplicationTool(Tool):
    name = "open_application"
    description = (
        "Open a desktop application by its short name, e.g. chrome, edge, firefox, "
        "vscode, explorer, spotify, notepad, calculator."
    )
    permission_level = PermissionLevel.LOW
    parameters = [
        ToolParameter(
            name="application",
            type="string",
            description="Short application key, e.g. 'chrome'.",
            required=True,
            enum=list(_FALLBACK_COMMANDS.keys()),
        )
    ]

    def __init__(self, applications: dict[str, ApplicationEntry]) -> None:
        self._applications = applications

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        key = str(arguments["application"]).strip().lower()
        executable = _resolve_executable(key, self._applications)
        if executable is None:
            return ToolResult.fail(
                error="application_not_found",
                message=f"I couldn't find {key} on this computer.",
            )

        if platform.system() != "Windows":
            logger.info(
                "Non-Windows platform detected; skipping real launch of '%s' (%s)",
                key,
                executable,
            )
            return ToolResult.ok(
                message=f"(simulated) Opening {key}.",
                executable=executable,
                simulated=True,
            )

        try:
            subprocess.Popen([executable], shell=False)  # noqa: S603
        except OSError as exc:
            logger.error("Failed to launch '%s': %s", key, exc)
            return ToolResult.fail(
                error=str(exc), message=f"I found {key} but couldn't launch it."
            )

        display_name = self._applications.get(key).display_name if key in self._applications else key
        return ToolResult.ok(message=f"Opening {display_name}.", executable=executable)
