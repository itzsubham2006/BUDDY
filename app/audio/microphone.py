"""
Microphone abstraction.

Wraps `sounddevice`/`pyaudio` so the rest of the app depends only on this
interface, not a specific audio library. Implemented fully in Phase 5;
this module currently defines the contract and a safe no-op fallback so
imports elsewhere never fail before the audio pipeline is wired up.
"""

from __future__ import annotations

import abc
import logging

logger = logging.getLogger("jarvis.audio.microphone")


class MicrophoneError(Exception):
    """Raised when the microphone is unavailable, permission is denied,
    or a read fails."""


class Microphone(abc.ABC):
    @abc.abstractmethod
    def is_available(self) -> bool:
        """Return True if a working input device can be opened."""
        raise NotImplementedError

    @abc.abstractmethod
    async def read_chunk(self, duration_seconds: float) -> bytes:
        """Capture `duration_seconds` of audio and return raw PCM bytes."""
        raise NotImplementedError


class NullMicrophone(Microphone):
    """Safe stand-in with no real hardware access. Used until Phase 5."""

    def is_available(self) -> bool:
        return False

    async def read_chunk(self, duration_seconds: float) -> bytes:
        raise MicrophoneError("No microphone backend is configured yet.")
