"""
Speech-to-text abstraction.

`transcribe(audio_bytes) -> text` is the contract the rest of the app
relies on. A local/offline implementation (`faster-whisper`) is the
default per spec section 11, keeping the app usable without an internet
connection or an API key. `NullSTT` is a safe stand-in used until a real
audio pipeline (Phase 5/6) is wired up, and in tests.
"""

from __future__ import annotations

import abc
import logging

logger = logging.getLogger("jarvis.speech.stt")


class STTError(Exception):
    """Raised when transcription fails."""


class SpeechToText(abc.ABC):
    @abc.abstractmethod
    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe raw audio (WAV PCM) to text. Raise STTError on
        unrecoverable failure; the caller decides how to react (e.g. ask
        the user to repeat themselves)."""
        raise NotImplementedError


class NullSTT(SpeechToText):
    """Placeholder used before the real audio pipeline is wired up."""

    async def transcribe(self, audio_bytes: bytes) -> str:
        raise STTError("No speech-to-text backend is configured yet.")


class WhisperLocalSTT(SpeechToText):
    """Offline transcription via `faster-whisper`."""

    def __init__(self, model_size: str = "base") -> None:
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise STTError(
                "faster-whisper is not installed. Run `pip install faster-whisper`."
            ) from exc
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")

    async def transcribe(self, audio_bytes: bytes) -> str:
        import io
        import wave

        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
                frames = wav_file.readframes(wav_file.getnframes())
        except Exception as exc:
            raise STTError(f"Invalid audio data: {exc}") from exc

        import numpy as np  # type: ignore

        audio_array = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self._model.transcribe(audio_array)
        return " ".join(segment.text.strip() for segment in segments).strip()


def create_stt(provider: str) -> SpeechToText:
    if provider == "whisper_local":
        try:
            return WhisperLocalSTT()
        except STTError as exc:
            logger.warning("%s STT will be unavailable until installed.", exc)
            return NullSTT()
    logger.warning("Unknown STT_PROVIDER '%s'; STT will be unavailable.", provider)
    return NullSTT()
