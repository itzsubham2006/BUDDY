"""
Speech-to-text abstraction and backends.

Supported providers:
- 'whisper_local': 100% offline using `faster-whisper` on CPU (int8).
- 'google_free': Free, fast online speech recognition via SpeechRecognition (0 API keys).
"""

from __future__ import annotations

import abc
import asyncio
import io
import logging
import wave

logger = logging.getLogger("buddy.speech.stt")


class STTError(Exception):
    """Raised when transcription fails."""


class SpeechToText(abc.ABC):
    @abc.abstractmethod
    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe raw WAV audio to text."""
        raise NotImplementedError


class NullSTT(SpeechToText):
    """Placeholder when no STT backend is available."""

    async def transcribe(self, audio_bytes: bytes) -> str:
        raise STTError("No speech-to-text backend is configured.")


class WhisperLocalSTT(SpeechToText):
    """Offline transcription via `faster-whisper`."""

    def __init__(self, model_size: str = "tiny.en") -> None:
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as exc:
            raise STTError(
                "faster-whisper is not installed. Run `pip install faster-whisper`."
            ) from exc
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")

    async def transcribe(self, audio_bytes: bytes) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_transcribe, audio_bytes)

    def _sync_transcribe(self, audio_bytes: bytes) -> str:
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
                frames = wav_file.readframes(wav_file.getnframes())
        except Exception as exc:
            raise STTError(f"Invalid audio data: {exc}") from exc

        import numpy as np  # type: ignore

        audio_array = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self._model.transcribe(audio_array)
        return " ".join(segment.text.strip() for segment in segments).strip()


class GoogleFreeSTT(SpeechToText):
    """Fast, free online speech recognition via SpeechRecognition (requires 0 keys)."""

    def __init__(self) -> None:
        try:
            import speech_recognition as sr  # type: ignore

            self._sr = sr
            self._recognizer = sr.Recognizer()
        except ImportError as exc:
            raise STTError(
                "SpeechRecognition is not installed. Run `pip install SpeechRecognition`."
            ) from exc

    async def transcribe(self, audio_bytes: bytes) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_transcribe, audio_bytes)

    def _sync_transcribe(self, audio_bytes: bytes) -> str:
        try:
            audio_file = io.BytesIO(audio_bytes)
            with self._sr.AudioFile(audio_file) as source:
                audio = self._recognizer.record(source)
            return self._recognizer.recognize_google(audio)
        except self._sr.UnknownValueError:
            return ""
        except Exception as exc:
            raise STTError(f"Google speech recognition failed: {exc}") from exc


def create_stt(provider: str = "whisper_local") -> SpeechToText:
    prov = (provider or "whisper_local").lower()
    if prov in ("whisper_local", "whisper", "local", "offline"):
        try:
            return WhisperLocalSTT()
        except STTError as exc:
            logger.warning("%s Falling back to GoogleFreeSTT.", exc)
            try:
                return GoogleFreeSTT()
            except Exception:
                return NullSTT()
    if prov in ("google", "google_free", "speech_recognition"):
        try:
            return GoogleFreeSTT()
        except STTError as exc:
            logger.warning("%s STT will be unavailable.", exc)
            return NullSTT()

    logger.warning("Unknown STT_PROVIDER '%s'; falling back to whisper_local.", provider)
    try:
        return WhisperLocalSTT()
    except Exception:
        return NullSTT()
