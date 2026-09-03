"""
Recorder: captures a single spoken utterance (after wake-word detection)
using silence-detection or a fixed timeout, and hands the resulting audio
to the STT layer.

Interface defined now; full implementation lands in Phase 5 alongside the
real Microphone backend.
"""

from __future__ import annotations

import abc
import logging

logger = logging.getLogger("jarvis.audio.recorder")


class RecorderError(Exception):
    """Raised when recording fails or times out with no speech detected."""


class UtteranceRecorder(abc.ABC):
    @abc.abstractmethod
    async def record_utterance(self, timeout_seconds: float) -> bytes:
        """Record until silence is detected or `timeout_seconds` elapses.
        Returns raw PCM audio bytes. Raises RecorderError on timeout with
        no speech captured."""
        raise NotImplementedError


class NullRecorder(UtteranceRecorder):
    """Safe stand-in used until the real audio pipeline (Phase 5) exists."""

    async def record_utterance(self, timeout_seconds: float) -> bytes:
        raise RecorderError("No audio recording backend is configured yet.")
