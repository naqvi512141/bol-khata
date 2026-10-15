"""Groq Hosted Whisper ASR implementation.

Per docs/04-stack.md §4:
model=whisper-large-v3, language=ur, task=transcribe, response_format=verbose_json, temperature=0.
NEVER log or print the GROQ_API_KEY.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import httpx

from app.asr.base import ASREngine
from app.asr.confidence import aggregate_segments_confidence
from app.ingest.audio import IngestedAudio
from app.schemas import ASRSegment, RawASRPayload

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class GroqASRError(Exception):
    """Exception raised when Groq ASR transcription fails."""

    def __init__(self, message: str, reason_category: str) -> None:
        super().__init__(message)
        self.reason_category = reason_category
        self.message = message


class GroqWhisperEngine(ASREngine):
    """ASR Engine backed by Groq Hosted whisper-large-v3."""

    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        # Validate that api_key is configured at initialization time
        if not api_key or not api_key.strip():
            raise ValueError("GROQ_API_KEY is required for GroqWhisperEngine")
        self._api_key = api_key.strip()
        self._client = client
        self._timeout = timeout

    def transcribe(
        self,
        audio: IngestedAudio,
        job_id: str,
        shop_id: str,
        draft_id: str | None = None,
        prompt: str = "",
        audio_ref: str = "",
    ) -> RawASRPayload:
        """Send audio to Groq API and parse response into RawASRPayload."""
        start_time = time.perf_counter()

        files: dict[str, tuple[str, bytes, str]] = {
            "file": ("audio.wav", audio.wav_bytes, "audio/wav"),
        }
        data: dict[str, Any] = {
            "model": "whisper-large-v3",
            "language": "ur",
            "task": "transcribe",  # AGENTS.md rule 4: NEVER task="translate"
            "response_format": "verbose_json",
            "temperature": 0,
        }
        if prompt:
            data["prompt"] = prompt

        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }

        try:
            if self._client is not None:
                response = self._client.post(
                    GROQ_TRANSCRIPTION_URL,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=self._timeout,
                )
            else:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(
                        GROQ_TRANSCRIPTION_URL,
                        headers=headers,
                        files=files,
                        data=data,
                    )
        except httpx.TimeoutException as e:
            raise GroqASRError("Groq API request timed out", reason_category="timeout") from e
        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise GroqASRError("Network error connecting to Groq API", reason_category="network_error") from e
        except Exception as e:
            raise GroqASRError(f"Groq API connection error: {type(e).__name__}", reason_category="network_error") from e

        if response.status_code == 401:
            raise GroqASRError("Groq API authentication failed (HTTP 401)", reason_category="auth_failure")
        elif response.status_code == 429:
            raise GroqASRError("Groq API rate limit exceeded (HTTP 429)", reason_category="rate_limit")
        elif response.status_code >= 500:
            raise GroqASRError(
                f"Groq API server error (HTTP {response.status_code})",
                reason_category="server_error",
            )
        elif response.status_code != 200:
            raise GroqASRError(
                f"Groq API returned HTTP {response.status_code}",
                reason_category="api_error",
            )

        try:
            resp_json = response.json()
        except Exception as e:
            raise GroqASRError("Failed to parse Groq response JSON", reason_category="api_error") from e

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0)
        raw_text = resp_json.get("text", "").strip()

        segments: list[ASRSegment] = []
        for s in resp_json.get("segments", []):
            segments.append(
                ASRSegment(
                    text=s.get("text", "").strip(),
                    start=float(s.get("start", 0.0)),
                    end=float(s.get("end", 0.0)),
                    avg_logprob=float(s.get("avg_logprob", 0.0)),
                    no_speech_prob=float(s.get("no_speech_prob", 0.0)),
                )
            )

        asr_conf = aggregate_segments_confidence(segments)
        bias_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16] if prompt else ""

        return RawASRPayload(
            job_id=job_id,
            shop_id=shop_id,
            draft_id=draft_id,
            engine="groq_whisper",
            model_name="whisper-large-v3",
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
