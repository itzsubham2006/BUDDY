"""
System-level tools: time, basic system info, and volume control.

Volume control uses `pycaw` on Windows (COM-based). On non-Windows
platforms (e.g. during development/tests on Linux/macOS) it degrades
gracefully and reports that the feature is unavailable rather than
crashing.
"""

from __future__ import annotations

import datetime
import platform
from typing import Any

from app.security.permissions import PermissionLevel
from app.tools.base import Tool, ToolResult


def _is_windows() -> bool:
    return platform.system() == "Windows"


class GetCurrentTimeTool(Tool):
    name = "get_current_time"
    description = "Get the current local time and date."
    permission_level = PermissionLevel.LOW
    parameters = []

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        now = datetime.datetime.now()
        formatted = now.strftime("%I:%M %p on %A, %B %d")
        return ToolResult.ok(message=f"It is {formatted}.", iso_time=now.isoformat())


class GetSystemInfoTool(Tool):
    name = "get_system_info"
    description = "Get basic information about this computer (OS, version, machine name)."
    permission_level = PermissionLevel.LOW
    parameters = []

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "node": platform.node(),
            "python_version": platform.python_version(),
        }
        message = f"You're running {info['os']} on {info['machine']}."
        return ToolResult.ok(message=message, **info)


class _VolumeToolBase(Tool):
    permission_level = PermissionLevel.LOW
    parameters = []

    def _unsupported_result(self) -> ToolResult:
        return ToolResult.fail(
            error="volume_control_unsupported_platform",
            message="Volume control is only implemented for Windows right now.",
        )

    def _get_volume_interface(self):  # pragma: no cover - requires Windows/pycaw
        from ctypes import cast, POINTER  # type: ignore
        from comtypes import CLSCTX_ALL  # type: ignore
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))


class VolumeUpTool(_VolumeToolBase):
    name = "volume_up"
    description = "Increase the system volume by a step (default 10%)."
    parameters = []

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        if not _is_windows():
            return self._unsupported_result()
        try:
            volume = self._get_volume_interface()  # pragma: no cover
            current = volume.GetMasterVolumeLevelScalar()  # pragma: no cover
            new_level = min(1.0, current + 0.1)  # pragma: no cover
            volume.SetMasterVolumeLevelScalar(new_level, None)  # pragma: no cover
            return ToolResult.ok(message="Volume increased.")  # pragma: no cover
        except Exception as exc:  # pragma: no cover
            return ToolResult.fail(error=str(exc), message="I couldn't change the volume.")


class VolumeDownTool(_VolumeToolBase):
    name = "volume_down"
    description = "Decrease the system volume by a step (default 10%)."
    parameters = []

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        if not _is_windows():
            return self._unsupported_result()
        try:
            volume = self._get_volume_interface()  # pragma: no cover
            current = volume.GetMasterVolumeLevelScalar()  # pragma: no cover
            new_level = max(0.0, current - 0.1)  # pragma: no cover
            volume.SetMasterVolumeLevelScalar(new_level, None)  # pragma: no cover
            return ToolResult.ok(message="Volume decreased.")  # pragma: no cover
        except Exception as exc:  # pragma: no cover
            return ToolResult.fail(error=str(exc), message="I couldn't change the volume.")


class MuteTool(_VolumeToolBase):
    name = "mute"
    description = "Mute system audio."
    parameters = []

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        if not _is_windows():
            return self._unsupported_result()
        try:
            volume = self._get_volume_interface()  # pragma: no cover
            volume.SetMute(1, None)  # pragma: no cover
            return ToolResult.ok(message="Muted.")  # pragma: no cover
        except Exception as exc:  # pragma: no cover
            return ToolResult.fail(error=str(exc), message="I couldn't mute the audio.")


class UnmuteTool(_VolumeToolBase):
    name = "unmute"
    description = "Unmute system audio."
    parameters = []

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        if not _is_windows():
            return self._unsupported_result()
        try:
            volume = self._get_volume_interface()  # pragma: no cover
            volume.SetMute(0, None)  # pragma: no cover
            return ToolResult.ok(message="Unmuted.")  # pragma: no cover
        except Exception as exc:  # pragma: no cover
            return ToolResult.fail(error=str(exc), message="I couldn't unmute the audio.")
