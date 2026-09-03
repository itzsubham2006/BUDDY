"""
File/folder opening tools.

These open a file or folder with the OS default handler (equivalent to
double-clicking it) — they do not read, modify, or delete content. Still
classified MEDIUM because they touch the filesystem and reveal paths.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from app.security.permissions import PermissionLevel
from app.tools.base import Tool, ToolParameter, ToolResult

logger = logging.getLogger("jarvis.tools.files")


def _safe_resolve(path_str: str) -> Path:
    """Expand user/env vars and resolve to an absolute path."""
    expanded = os.path.expandvars(os.path.expanduser(path_str))
    return Path(expanded).resolve()


class OpenFileTool(Tool):
    name = "open_file"
    description = "Open a specific file with its default application, given a path."
    permission_level = PermissionLevel.MEDIUM
    parameters = [
        ToolParameter(name="path", type="string", description="Path to the file to open.")
    ]

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        target = _safe_resolve(str(arguments["path"]))
        if not target.exists():
            return ToolResult.fail(
                error="file_not_found", message=f"I couldn't find that file: {target}"
            )
        if not target.is_file():
            return ToolResult.fail(
                error="not_a_file", message=f"That path isn't a file: {target}"
            )
        try:
            _open_with_default_app(target)
        except OSError as exc:
            logger.error("Failed to open file '%s': %s", target, exc)
            return ToolResult.fail(error=str(exc), message="I couldn't open that file.")
        return ToolResult.ok(message=f"Opening {target.name}.", path=str(target))


class OpenFolderTool(Tool):
    name = "open_folder"
    description = "Open a folder in File Explorer, given a path."
    permission_level = PermissionLevel.MEDIUM
    parameters = [
        ToolParameter(name="path", type="string", description="Path to the folder to open.")
    ]

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        target = _safe_resolve(str(arguments["path"]))
        if not target.exists():
            return ToolResult.fail(
                error="folder_not_found", message=f"I couldn't find that folder: {target}"
            )
        if not target.is_dir():
            return ToolResult.fail(
                error="not_a_folder", message=f"That path isn't a folder: {target}"
            )
        try:
            _open_with_default_app(target)
        except OSError as exc:
            logger.error("Failed to open folder '%s': %s", target, exc)
            return ToolResult.fail(error=str(exc), message="I couldn't open that folder.")
        return ToolResult.ok(message=f"Opening {target.name}.", path=str(target))


def _open_with_default_app(path: Path) -> None:
    system = platform.system()
    if system == "Windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.Popen(["open", str(path)], shell=False)  # noqa: S603
    else:
        subprocess.Popen(["xdg-open", str(path)], shell=False)  # noqa: S603
