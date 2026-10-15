"""ASR Engine protocol definition."""

from __future__ import annotations

from typing import Protocol

from app.ingest.audio import IngestedAudio
from app.schemas import RawASRPayload


class ASREngine(Protocol):
    """Protocol for an ASR Engine (Groq Whisper, Local Faster-Whisper, etc.)."""

    def transcribe(
        self,
        audio: IngestedAudio,
        job_id: str,
        shop_id: str,
        draft_id: str | None = None,
        prompt: str = "",
        audio_ref: str = "",
    ) -> RawASRPayload:
        """Transcribe ingested audio into RawASRPayload.

        Must set task="transcribe" and language="ur".
        """
        ...
