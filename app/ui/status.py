"""
Lightweight status surface.

Per spec section 24, V1 avoids a full GUI. This module offers Windows
toast-style notifications as an optional visual complement to voice
output — never required for the agent to function.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("jarvis.ui.status")


def notify(title: str, message: str) -> None:
    """Best-effort desktop notification. Never raises — a failure here
    should never interrupt the agent."""
    try:
        from plyer import notification  # type: ignore

        notification.notify(title=title, message=message, app_name="Jarvis", timeout=4)
    except Exception as exc:  # pragma: no cover - platform/env dependent
        logger.debug("Notification unavailable (%s); logging instead: %s - %s", exc, title, message)
