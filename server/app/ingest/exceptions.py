"""Audio ingestion exceptions with typed error codes.

Per docs/02-contracts.md §8:
400 -> {code, message} for audio_too_short, audio_too_long, bad_codec
"""

from __future__ import annotations


class AudioIngestError(Exception):
    """Base exception for audio ingestion failures."""

    code: str = "audio_ingest_error"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code
        self.message = message


class AudioTooShortError(AudioIngestError):
    """Raised when audio duration is shorter than 700 ms."""

    code = "audio_too_short"


class AudioTooLongError(AudioIngestError):
    """Raised when audio duration exceeds 20 seconds (20,000 ms)."""

    code = "audio_too_long"


class BadCodecError(AudioIngestError):
    """Raised when audio format/codec cannot be decoded."""

    code = "bad_codec"
