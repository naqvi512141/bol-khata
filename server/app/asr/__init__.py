"""ASR service module."""

from app.asr.base import ASREngine
from app.asr.bias import build_bias_prompt, estimate_token_count
from app.asr.confidence import aggregate_segments_confidence, compute_asr_confidence
from app.asr.groq_whisper import GroqASRError, GroqWhisperEngine
from app.asr.local_whisper import LocalWhisperEngine
from app.asr.service import ASRService

__all__ = [
    "ASREngine",
    "ASRService",
    "GroqASRError",
    "GroqWhisperEngine",
    "LocalWhisperEngine",
    "aggregate_segments_confidence",
    "build_bias_prompt",
    "compute_asr_confidence",
    "estimate_token_count",
]
