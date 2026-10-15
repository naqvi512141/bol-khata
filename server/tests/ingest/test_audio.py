"""Tests for audio ingestion and resampling.

Network-independent: generates synthetic audio in-memory with PyAV/wave.
"""

from __future__ import annotations

import io
import wave
import numpy as np
import pytest

from app.ingest.audio import process_audio
from app.ingest.exceptions import AudioTooLongError, AudioTooShortError, BadCodecError


def _generate_wav(duration_s: float, sample_rate: int = 44100, channels: int = 1, clip: bool = False) -> bytes:
    """Generate in-memory WAV bytes of a sine wave."""
    num_samples = int(duration_s * sample_rate)
    t = np.linspace(0, duration_s, num_samples, False)
    # 440 Hz tone
    if clip:
        samples = np.sin(2 * np.pi * 440 * t) * 5.0  # Cause heavy clipping
    else:
        samples = np.sin(2 * np.pi * 440 * t) * 0.7  # Clean unclipped tone
    int_samples = np.clip(samples * 32767, -32768, 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        if channels == 1:
            wf.writeframes(int_samples.tobytes())
        else:
            stereo = np.column_stack([int_samples, int_samples])
            wf.writeframes(stereo.tobytes())
    return buf.getvalue()


def test_process_valid_audio() -> None:
    """A valid 1.5s 44.1kHz stereo WAV is resampled to 16kHz mono."""
    raw = _generate_wav(duration_s=1.5, sample_rate=44100, channels=2)
    ingested = process_audio(raw)

    assert 1400 <= ingested.duration_ms <= 1600
    assert ingested.clip_ratio == 0.0

    # Verify the generated WAV header
    with wave.open(io.BytesIO(ingested.wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        n_frames = wf.getnframes()
        assert 22400 <= n_frames <= 25600


def test_process_audio_too_short() -> None:
    """Audio shorter than 700 ms is rejected with typed AudioTooShortError."""
    raw = _generate_wav(duration_s=0.5, sample_rate=16000)
    with pytest.raises(AudioTooShortError) as exc_info:
        process_audio(raw)
    assert exc_info.value.code == "audio_too_short"
    assert "shorter than minimum 700 ms" in str(exc_info.value)


def test_process_audio_too_long() -> None:
    """Audio longer than 20 s is rejected with typed AudioTooLongError."""
    raw = _generate_wav(duration_s=20.5, sample_rate=16000)
    with pytest.raises(AudioTooLongError) as exc_info:
        process_audio(raw)
    assert exc_info.value.code == "audio_too_long"
    assert "exceeds maximum 20000 ms" in str(exc_info.value)


def test_process_bad_codec_empty() -> None:
    """Empty or corrupt payload raises typed BadCodecError."""
    with pytest.raises(BadCodecError) as exc_info:
        process_audio(b"")
    assert exc_info.value.code == "bad_codec"

    with pytest.raises(BadCodecError) as exc_info2:
        process_audio(b"NOT_A_VALID_AUDIO_FILE_DATA")
    assert exc_info2.value.code == "bad_codec"


def test_process_clipped_audio() -> None:
    """Heavily clipped audio results in clip_ratio > 0."""
    raw = _generate_wav(duration_s=1.0, sample_rate=16000, clip=True)
    ingested = process_audio(raw)
    assert ingested.clip_ratio > 0.1
