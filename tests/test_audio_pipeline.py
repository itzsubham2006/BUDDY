from __future__ import annotations

import io
import wave
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.audio.microphone import NullMicrophone
from app.audio.recorder import EnergyVADRecorder, NullRecorder, pcm_to_wav
from app.audio.wake_word import LocalWakeWordDetector, NullWakeWordDetector


def test_pcm_to_wav_produces_valid_wav():
    fake_pcm = b"\x00\x00" * 1600  # 0.1s of 16kHz 16-bit audio
    wav_bytes = pcm_to_wav(fake_pcm, sample_rate=16000, channels=1)

    assert wav_bytes.startswith(b"RIFF")
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000
        assert wf.getsampwidth() == 2
        assert wf.getnframes() == 1600


@pytest.mark.asyncio
async def test_null_audio_components():
    mic = NullMicrophone()
    assert mic.is_available() is False

    rec = NullRecorder()
    with pytest.raises(Exception):
        await rec.record_utterance()

    detector = NullWakeWordDetector()
    with pytest.raises(Exception):
        await detector.wait_for_wake_word()


def test_wake_word_pattern_matching():
    detector = LocalWakeWordDetector(wake_word="Hi Buddy")
    assert detector._matches_wake_word("hi buddy can you hear me") is True
    assert detector._matches_wake_word("hey buddy what time is it") is True
    assert detector._matches_wake_word("buddy open chrome") is True
    assert detector._matches_wake_word("what is the weather today") is False
