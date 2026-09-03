"""
Utterance recorder with Voice Activity Detection (VAD).
"""

from __future__ import annotations

import abc
import asyncio
import io
import logging
import wave
from typing import Optional

import numpy as np

from app.audio.microphone import Microphone, NullMicrophone

logger = logging.getLogger("buddy.audio.recorder")


class RecorderError(Exception):
    """Raised when recording fails or times out with no speech detected."""


def pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Pack raw PCM bytes into a valid WAV format in-memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return buf.getvalue()


class UtteranceRecorder(abc.ABC):
    @abc.abstractmethod
    async def record_utterance(self, timeout_seconds: float = 8.0) -> bytes:
        """Record until silence is detected or `timeout_seconds` elapses. Return WAV bytes."""
        raise NotImplementedError


class EnergyVADRecorder(UtteranceRecorder):
    """
    Captures speech using energy thresholding (VAD).
    Waits for the user to start talking, then continues until they pause/stop.
    """

    def __init__(
        self,
        microphone: Microphone,
        sample_rate: int = 16000,
        energy_threshold: float = 30.0,
        silence_limit_seconds: float = 1.2,
    ) -> None:
        self._mic = microphone
        self.sample_rate = sample_rate
        self.energy_threshold = energy_threshold
        self.silence_limit_seconds = silence_limit_seconds

    async def record_utterance(self, timeout_seconds: float = 8.0) -> bytes:
        chunk_duration = 0.1  # 100ms chunks
        total_time = 0.0
        silence_time = 0.0
        speech_started = False
        captured_frames: list[bytes] = []

        while total_time < timeout_seconds:
            chunk = await self._mic.read_chunk(chunk_duration)
            total_time += chunk_duration
            captured_frames.append(chunk)

            # Calculate RMS energy of the chunk
            data_arr = np.frombuffer(chunk, dtype=np.int16)
            rms = np.sqrt(np.mean(np.square(data_arr.astype(np.float32)))) if len(data_arr) > 0 else 0

            if rms > self.energy_threshold:
                speech_started = True
                silence_time = 0.0
            elif speech_started:
                silence_time += chunk_duration
                if silence_time >= self.silence_limit_seconds:
                    # User finished speaking
                    break

        if not speech_started:
            raise RecorderError("No speech detected.")

        full_pcm = b"".join(captured_frames)
        return pcm_to_wav(full_pcm, sample_rate=self.sample_rate)


class NullRecorder(UtteranceRecorder):
    """Fallback when no microphone is available."""

    async def record_utterance(self, timeout_seconds: float = 8.0) -> bytes:
        raise RecorderError("No audio recording backend is configured.")


def create_recorder(microphone: Optional[Microphone] = None) -> UtteranceRecorder:
    if microphone is None or isinstance(microphone, NullMicrophone):
        return NullRecorder()
    return EnergyVADRecorder(microphone)
