"""
Microphone abstraction and implementation using sounddevice.
"""

from __future__ import annotations

import abc
import asyncio
import logging
from typing import Optional

logger = logging.getLogger("buddy.audio.microphone")


class MicrophoneError(Exception):
    """Raised when the microphone is unavailable, permission is denied, or a read fails."""


class Microphone(abc.ABC):
    @abc.abstractmethod
    def is_available(self) -> bool:
        """Return True if a working input device can be opened."""
        raise NotImplementedError

    @abc.abstractmethod
    async def read_chunk(self, duration_seconds: float) -> bytes:
        """Capture `duration_seconds` of audio and return raw PCM bytes (16kHz, 16-bit mono)."""
        raise NotImplementedError


class SoundDeviceMicrophone(Microphone):
    """Real microphone backend powered by `sounddevice`."""

    def __init__(self, sample_rate: int = 16000, device_index: Optional[int] = None) -> None:
        self.sample_rate = sample_rate
        self.device_index = device_index
        try:
            import sounddevice as sd  # type: ignore

            self._sd = sd
        except ImportError as exc:
            raise MicrophoneError("sounddevice is not installed. Run `pip install sounddevice`.") from exc

    def is_available(self) -> bool:
        try:
            devices = self._sd.query_devices()
            # Check if any input device has > 0 input channels
            return any(d.get("max_input_channels", 0) > 0 for d in devices)
        except Exception:
            return False

    async def read_chunk(self, duration_seconds: float) -> bytes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_read_chunk, duration_seconds)

    def _sync_read_chunk(self, duration_seconds: float) -> bytes:
        frames = int(duration_seconds * self.sample_rate)
        try:
            audio_array = self._sd.rec(
                frames,
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                device=self.device_index,
            )
            self._sd.wait()
            return audio_array.tobytes()
        except Exception as exc:
            raise MicrophoneError(f"Failed capturing audio from microphone: {exc}") from exc


class NullMicrophone(Microphone):
    """Safe fallback with no hardware access."""

    def is_available(self) -> bool:
        return False

    async def read_chunk(self, duration_seconds: float) -> bytes:
        raise MicrophoneError("No microphone backend is configured.")


def create_microphone() -> Microphone:
    try:
        mic = SoundDeviceMicrophone()
        if mic.is_available():
            return mic
        logger.warning("No working microphone input device found; using NullMicrophone.")
        return NullMicrophone()
    except Exception as exc:
        logger.warning("Could not initialize sounddevice microphone (%s); using NullMicrophone.", exc)
        return NullMicrophone()
