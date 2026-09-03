"""
Long-term memory: explicitly-approved user preferences persisted to disk.

Design intent (see spec section 17): Jarvis must NOT silently remember
everything the user says. Something is only written here when the
orchestrator (in response to a clear user instruction like "remember
that...") calls `remember()`. This keeps long-term memory small,
inspectable, and revocable.

The storage backend is a plain JSON file for V1. The interface is kept
narrow (`remember` / `recall` / `forget` / `all`) so a vector database or
SQLite backend can be swapped in later without touching call sites.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.memory.long_term")


class LongTermMemory:
    def __init__(self, store_path: Path) -> None:
        self._store_path = store_path
        self._lock = threading.Lock()
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._store_path.exists():
            self._write({})

    def _read(self) -> dict[str, str]:
        try:
            with self._store_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            logger.warning("Long-term memory file missing/corrupt; starting fresh.")
            return {}

    def _write(self, data: dict[str, str]) -> None:
        with self._store_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def remember(self, key: str, value: str) -> None:
        with self._lock:
            data = self._read()
            data[key] = value
            self._write(data)
        logger.info("Remembered preference: %s", key)

    def recall(self, key: str) -> Optional[str]:
        with self._lock:
            return self._read().get(key)

    def forget(self, key: str) -> bool:
        with self._lock:
            data = self._read()
            if key in data:
                del data[key]
                self._write(data)
                logger.info("Forgot preference: %s", key)
                return True
            return False

    def all(self) -> dict[str, str]:
        with self._lock:
            return dict(self._read())
