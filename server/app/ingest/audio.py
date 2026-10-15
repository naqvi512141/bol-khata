"""In-memory audio ingestion and resampling using PyAV.

Resamples any input container/codec (WebM, Opus, WAV, MP3, etc.) to 16 kHz mono s16le WAV.
Enforces duration boundaries: rejects < 700 ms or > 20 s per docs/03-build-plan.md Phase 5.
"""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass

import av
import numpy as np

from app.ingest.exceptions import AudioTooLongError, AudioTooShortError, BadCodecError

MIN_DURATION_MS: int = 700
MAX_DURATION_MS: int = 20000
TARGET_SAMPLE_RATE: int = 16000


@dataclass(frozen=True)
class IngestedAudio:
    """Normalized audio ready for ASR."""

    wav_bytes: bytes
    duration_ms: int
    clip_ratio: float
    pcm_samples: np.ndarray


def process_audio(raw_bytes: bytes) -> IngestedAudio:
    """Decode and resample audio in-memory to 16 kHz mono s16le PCM WAV.

    Args:
        raw_bytes: Raw audio file bytes in any format supported by FFmpeg/PyAV.

    Returns:
        IngestedAudio with valid 16 kHz mono WAV bytes, duration_ms, and clip_ratio.

    Raises:
        BadCodecError: If raw_bytes cannot be parsed or decoded.
        AudioTooShortError: If duration_ms < 700 ms.
        AudioTooLongError: If duration_ms > 20000 ms.
    """
    if not raw_bytes:
        raise BadCodecError("Empty audio payload received")

    input_buf = io.BytesIO(raw_bytes)
    resampler = av.audio.resampler.AudioResampler(
        format="s16",
        layout="mono",
        rate=TARGET_SAMPLE_RATE,
    )
    raw_pcm = bytearray()

    try:
        with av.open(input_buf, mode="r") as container:
            if not container.streams.audio:
                raise BadCodecError("No audio streams found in media container")
            for frame in container.decode(audio=0):
                resampled_frames = resampler.resample(frame)
                if resampled_frames:
                    for rf in resampled_frames:
                        raw_pcm.extend(rf.to_ndarray().tobytes())
            # Flush any remaining audio in the resampler
            flushed = resampler.resample(None)
            if flushed:
                for rf in flushed:
                    raw_pcm.extend(rf.to_ndarray().tobytes())
    except (av.error.FFmpegError, Exception) as e:
        if isinstance(e, BadCodecError):
            raise
        raise BadCodecError(f"PyAV audio decoding failed: {e}") from e

    num_samples = len(raw_pcm) // 2  # 16-bit mono = 2 bytes per sample
    duration_ms = round(num_samples / float(TARGET_SAMPLE_RATE) * 1000.0)

    if duration_ms < MIN_DURATION_MS:
        raise AudioTooShortError(
            f"Audio duration {duration_ms} ms is shorter than minimum {MIN_DURATION_MS} ms"
        )
    if duration_ms > MAX_DURATION_MS:
        raise AudioTooLongError(
            f"Audio duration {duration_ms} ms exceeds maximum {MAX_DURATION_MS} ms"
        )

    samples = np.frombuffer(raw_pcm, dtype=np.int16)
    clip_ratio = float(np.mean(np.abs(samples) >= 32767)) if len(samples) > 0 else 0.0

    # Package into 16 kHz mono 16-bit PCM WAV
    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(TARGET_SAMPLE_RATE)
        wf.writeframes(raw_pcm)

    wav_bytes = wav_buf.getvalue()

    return IngestedAudio(
        wav_bytes=wav_bytes,
        duration_ms=duration_ms,
        clip_ratio=clip_ratio,
        pcm_samples=samples,
    )
