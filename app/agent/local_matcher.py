"""
Local deterministic command matcher.

Enables Buddy to run completely offline without an LLM or cloud API keys.
Interprets basic computer-control intents (launching any system or desktop app,
volume control, mute, system info, time, web/YouTube search) and maps them
to concrete ToolCall objects.
"""

from __future__ import annotations

import re
from typing import Optional

from app.llm.models import ToolCall

# Mapping for common app synonyms to known application keys
_APP_SYNONYMS: dict[str, str] = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "edge",
    "microsoft edge": "edge",
    "firefox": "firefox",
    "mozilla firefox": "firefox",
    "vscode": "vscode",
    "vs code": "vscode",
    "code": "vscode",
    "visual studio code": "vscode",
    "explorer": "explorer",
    "file explorer": "explorer",
    "files": "explorer",
    "spotify": "spotify",
    "notepad": "notepad",
    "calculator": "calculator",
    "calc": "calculator",
    "paint": "paint",
    "settings": "settings",
    "windows settings": "settings",
    "task manager": "task manager",
    "taskmgr": "task manager",
    "control panel": "control panel",
    "terminal": "terminal",
    "windows terminal": "terminal",
    "cmd": "cmd",
    "command prompt": "cmd",
    "powershell": "powershell",
    "camera": "camera",
    "clock": "clock",
    "alarm": "clock",
    "snipping tool": "snipping tool",
    "snip": "snipping tool",
}

_DIRECT_APP_NAMES = {
    "calculator",
    "calc",
    "notepad",
    "spotify",
    "paint",
    "settings",
    "task manager",
    "control panel",
    "terminal",
    "cmd",
    "powershell",
    "camera",
    "clock",
    "snipping tool",
}


class LocalCommandMatcher:
    """Matches user input against known local computer-control commands."""

    def match(self, text: str) -> Optional[ToolCall]:
        """Try to match `text` to a known ToolCall. Return None if not recognized."""
        cleaned = text.strip().lower()
        if not cleaned:
            return None

        # Strip trailing punctuation
        cleaned = re.sub(r"[?!.,;:]+$", "", cleaned).strip()

        # 1. Volume & Audio controls
        if self._matches_any(
            cleaned,
            [
                r"^(turn\s+)?volume\s*up$",
                r"^increase\s+(the\s+)?volume$",
                r"^turn\s+up(\s+the)?\s+volume$",
                r"^raise\s+(the\s+)?volume$",
                r"^louder$",
            ],
        ):
            return ToolCall(name="volume_up", arguments={})

        if self._matches_any(
            cleaned,
            [
                r"^(turn\s+)?volume\s*down$",
                r"^decrease\s+(the\s+)?volume$",
                r"^turn\s+down(\s+the)?\s+volume$",
                r"^lower\s+(the\s+)?volume$",
                r"^quieter$",
            ],
        ):
            return ToolCall(name="volume_down", arguments={})

        if self._matches_any(
            cleaned,
            [
                r"^mute(\s+audio|\s+sound|\s+volume)?$",
                r"^silence$",
            ],
        ):
            return ToolCall(name="mute", arguments={})

        if self._matches_any(
            cleaned,
            [
                r"^unmute(\s+audio|\s+sound|\s+volume)?$",
            ],
        ):
            return ToolCall(name="unmute", arguments={})

        # 2. Time & Date
        if self._matches_any(
            cleaned,
            [
                r"^(what('s|\s+is)\s+)?the\s+time(\s+now|\s+please)?$",
                r"^what\s+time\s+is\s+it$",
                r"^tell\s+me\s+the\s+time$",
                r"^current\s+time$",
                r"^time$",
            ],
        ):
            return ToolCall(name="get_current_time", arguments={})

        # 3. System Info
        if self._matches_any(
            cleaned,
            [
                r"^(get\s+|show\s+)?system\s+(info|information|status)$",
                r"^system\s*specs$",
                r"^(get\s+|show\s+)?pc\s+(info|status|specs)$",
                r"^specs$",
            ],
        ):
            return ToolCall(name="get_system_info", arguments={})

        # 4. YouTube
        m = re.match(r"^play\s+(.+?)(?:\s+on\s+youtube)?$", cleaned)
        if m:
            query = m.group(1).strip()
            if query:
                return ToolCall(name="play_youtube", arguments={"query": query})

        m = re.match(r"^(?:search\s+youtube\s+for|youtube)\s+(.+)$", cleaned)
        if m:
            query = m.group(1).strip()
            if query:
                return ToolCall(name="search_youtube", arguments={"query": query})

        # 5. Web Search & Browser
        m = re.match(
            r"^(?:search\s+(?:the\s+)?(?:web|internet|google)\s+for|google|search\s+for)\s+(.+)$",
            cleaned,
        )
        if m:
            query = m.group(1).strip()
            if query:
                return ToolCall(name="search_web", arguments={"query": query})

        m = re.match(
            r"^(?:open\s+(?:browser|the\s+browser|web\s+browser)|(?:go\s+to|open|browse\s+to)\s+(https?://\S+|\S+\.(?:com|org|net|io|edu|gov|dev)\S*))$",
            cleaned,
        )
        if m:
            url = m.group(1) if m.lastindex else None
            return ToolCall(name="open_browser", arguments={"url": url} if url else {})

        # 6. Applications
        # Direct application names (e.g. "paint", "settings", "task manager")
        if cleaned in _DIRECT_APP_NAMES:
            app_target = _APP_SYNONYMS.get(cleaned, cleaned)
            return ToolCall(name="open_application", arguments={"application": app_target})

        # "open/launch/start/run <target>"
        m = re.match(r"^(?:open|launch|start|run)\s+(.+)$", cleaned)
        if m:
            target = m.group(1).strip()
            if target.startswith("file "):
                return ToolCall(name="open_file", arguments={"path": target[5:].strip()})
            if target.startswith("folder ") or target.startswith("directory "):
                folder_path = target.split(" ", 1)[1].strip()
                return ToolCall(name="open_folder", arguments={"path": folder_path})

            # Check app synonym or pass directly to open_application
            app_target = _APP_SYNONYMS.get(target, target)
            return ToolCall(name="open_application", arguments={"application": app_target})

        return None

    @staticmethod
    def _matches_any(text: str, patterns: list[str]) -> bool:
        return any(re.search(pattern, text) is not None for pattern in patterns)
