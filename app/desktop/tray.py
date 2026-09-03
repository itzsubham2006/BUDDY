"""
Windows system tray integration.

Uses `pystray` so Jarvis can run with no visible console window. Full
wiring into the running agent loop (status icon updates, pause/resume)
lands in Phase 7; this module defines the states/menu contract so other
phases can be built against a stable interface.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger("jarvis.desktop.tray")


class TrayStatus(Enum):
    LISTENING = "Listening"
    PROCESSING = "Processing"
    SPEAKING = "Speaking"
    PAUSED = "Paused"
    ERROR = "Error"


class TrayApp:
    """
    Thin wrapper around `pystray.Icon`. Instantiate once from `main.py`
    and call `update_status()` as the agent moves through states.
    """

    def __init__(
        self,
        app_name: str,
        on_pause: Optional[Callable[[], None]] = None,
        on_resume: Optional[Callable[[], None]] = None,
        on_settings: Optional[Callable[[], None]] = None,
        on_open_logs: Optional[Callable[[], None]] = None,
        on_restart: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
    ) -> None:
        self._app_name = app_name
        self._callbacks = {
            "pause": on_pause,
            "resume": on_resume,
            "settings": on_settings,
            "open_logs": on_open_logs,
            "restart": on_restart,
            "exit": on_exit,
        }
        self._icon = None
        self._status = TrayStatus.PAUSED

    def _build_icon_image(self, status: TrayStatus):  # pragma: no cover - visual only
        from PIL import Image, ImageDraw

        colors = {
            TrayStatus.LISTENING: (46, 204, 113),
            TrayStatus.PROCESSING: (241, 196, 15),
            TrayStatus.SPEAKING: (52, 152, 219),
            TrayStatus.PAUSED: (149, 165, 166),
            TrayStatus.ERROR: (231, 76, 60),
        }
        color = colors.get(status, (149, 165, 166))
        image = Image.new("RGB", (64, 64), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, 56, 56), fill=color)
        return image

    def _build_menu(self):  # pragma: no cover - requires pystray at runtime
        import pystray

        def _call(key: str):
            def handler(icon, item):
                cb = self._callbacks.get(key)
                if cb:
                    cb()
            return handler

        return pystray.Menu(
            pystray.MenuItem(f"Status: {self._status.value}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Pause Listening", _call("pause")),
            pystray.MenuItem("Resume Listening", _call("resume")),
            pystray.MenuItem("Settings", _call("settings")),
            pystray.MenuItem("Open Logs", _call("open_logs")),
            pystray.MenuItem("Restart", _call("restart")),
            pystray.MenuItem("Exit", _call("exit")),
        )

    def run(self) -> None:  # pragma: no cover - blocks, requires GUI/tray support
        import pystray

        self._icon = pystray.Icon(
            self._app_name,
            icon=self._build_icon_image(self._status),
            title=f"{self._app_name} - {self._status.value}",
            menu=self._build_menu(),
        )
        self._icon.run()

    def update_status(self, status: TrayStatus) -> None:
        self._status = status
        if self._icon is not None:  # pragma: no cover
            self._icon.icon = self._build_icon_image(status)
            self._icon.title = f"{self._app_name} - {status.value}"
            self._icon.menu = self._build_menu()
        logger.debug("Tray status -> %s", status.value)

    def stop(self) -> None:
        if self._icon is not None:  # pragma: no cover
            self._icon.stop()
