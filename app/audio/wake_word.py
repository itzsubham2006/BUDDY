"""
Wake-word detector.

Per spec section 10: the wake-word system must NOT stream continuous
microphone audio to the LLM or any cloud API. A lightweight local
detector (e.g. Porcupine, or an openWakeWord model) listens continuously
on-device; only after it fires does the app start full recording +
transcription.

Full implementation lands in Phase 6. This module defines the contract
so the orchestrator/main loop can be written against it now.
"""

from __future__ import annotations

import abc
import logging

logger = logging.getLogger("jarvis.audio.wake_word")


class WakeWordError(Exception):
    """Raised when the wake-word engine fails to initialize or run."""


class WakeWordDetector(abc.ABC):
    @abc.abstractmethod
    async def wait_for_wake_word(self) -> None:
        """Block (async) until the configured wake word is detected."""
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop listening, releasing any audio resources."""
        raise NotImplementedError


class NullWakeWordDetector(WakeWordDetector):
    """Safe stand-in used until a real local wake-word engine (Phase 6) is wired up."""

    async def wait_for_wake_word(self) -> None:
        raise WakeWordError("No wake-word engine is configured yet.")

    def stop(self) -> None:
        return None
