"""
Text-to-speech abstraction.

`speak(text)` is the only method the rest of the app depends on, so the
backend can be swapped (pyttsx3 offline, edge-tts, Azure, OpenAI TTS)
without touching callers. `ConsoleTTS` is used whenever no audio backend
is available (e.g. during development, tests, or headless runs) so the
app always has somewhere to "speak" to.
"""

from __future__ import annotations

import abc
import logging

logger = logging.getLogger("jarvis.speech.tts")


class TTSError(Exception):
    """Raised when speech synthesis/playback fails."""


class TextToSpeech(abc.ABC):
    @abc.abstractmethod
    async def speak(self, text: str) -> None:
        """Synthesize and play `text`. Should not raise for expected
        failures (missing audio device, etc.) — log and return instead,
        so a TTS failure never crashes the agent loop."""
        raise NotImplementedError


class ConsoleTTS(TextToSpeech):
    """Fallback that just prints — always available, used by default/tests."""

    async def speak(self, text: str) -> None:
        print(f"🔊 Buddy: {text}")


class Pyttsx3TTS(TextToSpeech):
    """Offline TTS via `pyttsx3` (Windows SAPI5 under the hood)."""

    def __init__(self) -> None:
        try:
            import pyttsx3  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise TTSError(
                "pyttsx3 is not installed. Run `pip install pyttsx3`."
            ) from exc
        self._engine = pyttsx3.init()

    async def speak(self, text: str) -> None:
        try:
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception as exc:  # pragma: no cover - hardware dependent
            logger.error("TTS playback failed: %s", exc)


def create_tts(provider: str) -> TextToSpeech:
    if provider == "pyttsx3":
        try:
            return Pyttsx3TTS()
        except TTSError as exc:
            logger.warning("%s Falling back to console output.", exc)
            return ConsoleTTS()
    if provider == "console":
        return ConsoleTTS()
    logger.warning("Unknown TTS_PROVIDER '%s'; falling back to console.", provider)
    return ConsoleTTS()
