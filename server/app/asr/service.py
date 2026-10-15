"""ASR Service coordinating Groq and Local Whisper with failover.

Handles engine selection and automatic failover per docs/03-build-plan.md Phase 5.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.asr.base import ASREngine
from app.asr.bias import build_bias_prompt
from app.asr.groq_whisper import GroqASRError, GroqWhisperEngine
from app.asr.local_whisper import LocalWhisperEngine
from app.config import Settings, get_settings
from app.ingest.audio import IngestedAudio
from app.schemas import SKU, Customer, RawASRPayload

logger = logging.getLogger(__name__)


class ASRService:
    """ASR Service providing transcription with automatic failover."""

    def __init__(
        self,
        settings: Settings | None = None,
        groq_engine: ASREngine | None = None,
        local_engine: ASREngine | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.primary_engine_name = self.settings.ASR_ENGINE.lower().strip()

        # Distinguish missing key (configuration error, fail fast)
        if (
            self.primary_engine_name == "groq"
            and not groq_engine
            and (not self.settings.GROQ_API_KEY or not self.settings.GROQ_API_KEY.strip())
        ):
            raise ValueError(
                "ASR_ENGINE is configured as 'groq' but GROQ_API_KEY is missing or empty. "
                "Please configure GROQ_API_KEY in .env or set ASR_ENGINE='local'."
            )

        self.groq_engine: ASREngine | None
        if groq_engine is not None:
            self.groq_engine = groq_engine
        elif self.settings.GROQ_API_KEY and self.settings.GROQ_API_KEY.strip():
            self.groq_engine = GroqWhisperEngine(api_key=self.settings.GROQ_API_KEY)
        else:
            self.groq_engine = None

        self.local_engine = local_engine or LocalWhisperEngine()

    def transcribe(
        self,
        audio: IngestedAudio,
        job_id: str,
        shop_id: str,
        draft_id: str | None = None,
        catalogue: Sequence[SKU] | None = None,
        customers: Sequence[Customer] | None = None,
        audio_ref: str = "",
    ) -> RawASRPayload:
        """Transcribe audio with automatic failover from Groq to Local Whisper.

        If primary engine is 'groq', tries Groq first. On runtime API failure
        (auth failure, network error, timeout, rate limit), logs a WARNING with
        the reason category (never the API key) and fails over to local whisper.
        """
        bias_prompt = build_bias_prompt(catalogue=catalogue, customers=customers)

        if self.primary_engine_name == "groq" and self.groq_engine is not None:
            try:
                return self.groq_engine.transcribe(
                    audio=audio,
                    job_id=job_id,
                    shop_id=shop_id,
                    draft_id=draft_id,
                    prompt=bias_prompt,
                    audio_ref=audio_ref,
                )
            except GroqASRError as e:
                reason = e.reason_category
                logger.warning(
                    "Groq ASR failed with reason: %s. Failing over to local faster-whisper.",
                    reason,
                )
                payload = self.local_engine.transcribe(
                    audio=audio,
                    job_id=job_id,
                    shop_id=shop_id,
                    draft_id=draft_id,
                    prompt=bias_prompt,
                    audio_ref=audio_ref,
                )
                payload.failover_reason = reason
                return payload
            except Exception as e:  # noqa: BLE001 - catch all runtime failures to guarantee failover
                reason = "unexpected_error"
                logger.warning(
                    "Groq ASR unexpected failure: %s. Failing over to local faster-whisper.",
                    type(e).__name__,
                )
                payload = self.local_engine.transcribe(
                    audio=audio,
                    job_id=job_id,
                    shop_id=shop_id,
                    draft_id=draft_id,
                    prompt=bias_prompt,
                    audio_ref=audio_ref,
                )
                payload.failover_reason = reason
                return payload

        # Default or fallback path is local
        return self.local_engine.transcribe(
            audio=audio,
            job_id=job_id,
            shop_id=shop_id,
            draft_id=draft_id,
            prompt=bias_prompt,
            audio_ref=audio_ref,
        )
