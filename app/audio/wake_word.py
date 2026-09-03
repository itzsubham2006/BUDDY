"""
Wake-word detector for 'Hi Buddy'.

Listens continuously on-device. Uses adaptive noise calibration and phonetic
matching to reliably detect when the user calls 'Hi Buddy', 'Hey Buddy', or 'Buddy'.
"""

from __future__ import annotations

import abc
import asyncio
import logging
import re
from typing import Optional

import numpy as np

from app.audio.microphone import Microphone, NullMicrophone
from app.audio.recorder import pcm_to_wav
from app.speech.stt import SpeechToText, create_stt

logger = logging.getLogger("buddy.audio.wake_word")


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


class LocalWakeWordDetector(WakeWordDetector):
    """
    On-device wake-word detector.
    Monitors audio energy with auto-calibrated threshold and matches against 'Hi Buddy'.
    """

    def __init__(
        self,
        wake_word: str = "Hi Buddy",
        microphone: Optional[Microphone] = None,
        stt: Optional[SpeechToText] = None,
        energy_threshold: Optional[float] = None,
    ) -> None:
        self.wake_word = wake_word.strip().lower()
        self._mic = microphone
        self._stt = stt or create_stt("whisper_local")
        self.energy_threshold = energy_threshold  # None means auto-calibrate
        self._running = True

        # Common phonetic variations that speech recognition may produce for "Buddy" / "Hi Buddy"
        self._patterns = [
            r"\bhi\s+buddy\b",
            r"\bhey\s+buddy\b",
            r"\bhello\s+buddy\b",
            r"\bok(ay)?\s+buddy\b",
            r"\bbuddy\b",
            r"\bbuddie\b",
            r"\bhi\s+body\b",
            r"\bhey\s+body\b",
            r"\bbody\b",
            r"\bbud\b",
            r"\bjarvis\b",
        ]
        custom_escaped = re.escape(self.wake_word)
        if custom_escaped not in self._patterns:
            self._patterns.append(rf"\b{custom_escaped}\b")

    def stop(self) -> None:
        self._running = False

    async def _calibrate_noise(self) -> float:
        """Measure ambient noise for 0.4 seconds to set sensitive trigger threshold."""
        if self._mic is None:
            return 25.0
        try:
            sample = await self._mic.read_chunk(0.4)
            arr = np.frombuffer(sample, dtype=np.int16)
            rms = float(np.sqrt(np.mean(np.square(arr.astype(np.float32))))) if len(arr) > 0 else 10.0
            return max(rms, 8.0)
        except Exception:
            return 15.0

    async def wait_for_wake_word(self) -> None:
        if self._mic is None or isinstance(self._mic, NullMicrophone):
            raise WakeWordError("No working microphone available for wake word detection.")

        self._running = True

        # Auto-calibrate if not set
        if self.energy_threshold is None:
            ambient = await self._calibrate_noise()
            # Set trigger to 2x ambient, capped between 20.0 and 80.0
            self.energy_threshold = min(max(ambient * 2.0, 20.0), 80.0)
            logger.info("Microphone calibrated: ambient RMS=%.1f, trigger threshold=%.1f", ambient, self.energy_threshold)

        logger.info("Listening for wake word: '%s' (threshold=%.1f)...", self.wake_word, self.energy_threshold)

        chunk_sec = 0.2  # 200ms
        window_frames: list[bytes] = []
        max_window_chunks = 10  # ~2.0 seconds window

        while self._running:
            try:
                chunk = await self._mic.read_chunk(chunk_sec)
            except Exception as exc:
                logger.warning("Microphone read error: %s", exc)
                await asyncio.sleep(0.5)
                continue

            window_frames.append(chunk)
            if len(window_frames) > max_window_chunks:
                window_frames.pop(0)

            # Check RMS energy of current chunk
            data_arr = np.frombuffer(chunk, dtype=np.int16)
            rms = float(np.sqrt(np.mean(np.square(data_arr.astype(np.float32))))) if len(data_arr) > 0 else 0.0

            if rms > self.energy_threshold and len(window_frames) >= 3:
                logger.debug("Sound detected (RMS=%.1f > %.1f), capturing phrase...", rms, self.energy_threshold)

                # Capture an extra 0.8s to catch the end of "Buddy"
                extra_chunks = []
                for _ in range(4):
                    if not self._running:
                        return
                    extra = await self._mic.read_chunk(0.2)
                    extra_chunks.append(extra)

                full_pcm = b"".join(window_frames + extra_chunks)
                wav_data = pcm_to_wav(full_pcm)

                try:
                    transcription = await self._stt.transcribe(wav_data)
                    cleaned = transcription.strip().lower()
                    if cleaned:
                        logger.info("Heard ambient sound: '%s'", cleaned)

                    if self._matches_wake_word(cleaned):
                        logger.info("Wake word matched: '%s'!", cleaned)
                        return
                except Exception as exc:
                    logger.debug("Wake transcription error: %s", exc)

                window_frames.clear()
                await asyncio.sleep(0.2)

            await asyncio.sleep(0.04)

    def _matches_wake_word(self, text: str) -> bool:
        if not text:
            return False
        # Direct substring check for maximum reliability
        if "buddy" in text or "body" in text or "bud" in text or "jarvis" in text:
            return True
        return any(re.search(pat, text, re.IGNORECASE) is not None for pat in self._patterns)


class NullWakeWordDetector(WakeWordDetector):
    """Fallback when no microphone is present."""

    async def wait_for_wake_word(self) -> None:
        raise WakeWordError("No wake-word engine is configured.")

    def stop(self) -> None:
        pass


def create_wake_word_detector(
    wake_word: str = "Hi Buddy",
    microphone: Optional[Microphone] = None,
    stt: Optional[SpeechToText] = None,
) -> WakeWordDetector:
    if microphone is None or isinstance(microphone, NullMicrophone):
        return NullWakeWordDetector()
    return LocalWakeWordDetector(wake_word=wake_word, microphone=microphone, stt=stt)
