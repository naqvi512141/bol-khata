"""Local Faster-Whisper ASR implementation.

Uses faster-whisper small int8 on CPU.
Enforces AGENTS.md rule 4 (task="transcribe", language="ur") and rule 5 (condition_on_previous_text=False).
"""

from __future__ import annotations

import hashlib
import io
import time
from typing import Any

from app.asr.base import ASREngine
from app.asr.confidence import aggregate_segments_confidence
from app.ingest.audio import IngestedAudio
from app.schemas import ASRSegment, RawASRPayload


class LocalWhisperEngine(ASREngine):
    """ASR Engine backed by local faster-whisper small int8."""

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        model_instance: Any = None,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = model_instance

    def _get_model(self) -> Any:
        """Lazy-load the WhisperModel instance to prevent blocking startup/tests."""
        if self._model is None:
            from faster_whisper import WhisperModel  # type: ignore[import-untyped]

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def transcribe(
        self,
        audio: IngestedAudio,
        job_id: str,
        shop_id: str,
        draft_id: str | None = None,
        prompt: str = "",
        audio_ref: str = "",
    ) -> RawASRPayload:
        """Transcribe ingested audio using local faster-whisper."""
        start_time = time.perf_counter()
        model = self._get_model()

        # Audio can be passed as a binary stream of the 16 kHz WAV
        audio_file = io.BytesIO(audio.wav_bytes)

        # AGENTS.md rules 4 & 5:
        # task="transcribe", language="ur", condition_on_previous_text=False
        segments_generator, _ = model.transcribe(
            audio_file,
            language="ur",
            task="transcribe",
            condition_on_previous_text=False,
            initial_prompt=prompt if prompt else None,
            temperature=0.0,
        )

        segments: list[ASRSegment] = []
        text_parts: list[str] = []

        for seg in segments_generator:
            clean_text = seg.text.strip()
            if clean_text:
                text_parts.append(clean_text)
            segments.append(
                ASRSegment(
                    text=clean_text,
                    start=float(seg.start),
                    end=float(seg.end),
                    avg_logprob=float(seg.avg_logprob),
                    no_speech_prob=float(seg.no_speech_prob),
                )
            )

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0)
        raw_text = " ".join(text_parts).strip()
        asr_conf = aggregate_segments_confidence(segments)
        bias_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16] if prompt else ""

        return RawASRPayload(
            job_id=job_id,
            shop_id=shop_id,
            draft_id=draft_id,
            engine="local_faster_whisper",
            model_name=f"{self.model_size}-{self.compute_type}",
            language="ur",
            raw_text=raw_text,
            segments=segments,
            asr_confidence=asr_conf,
            audio_ref=audio_ref or f"audio_{job_id}.wav",
            duration_ms=audio.duration_ms,
            clip_ratio=audio.clip_ratio,
            bias_prompt_hash=bias_hash,
            processing_ms=elapsed_ms,
            failover_reason=None,
        )
