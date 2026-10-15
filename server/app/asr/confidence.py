"""ASR confidence computation.

Per docs/02-contracts.md §5:
asr_conf = math.exp(min(avg_logprob, 0.0))          # (0, 1]
if no_speech_prob > 0.6:
    asr_conf *= 0.3
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.schemas import ASRSegment


def compute_asr_confidence(avg_logprob: float, no_speech_prob: float = 0.0) -> float:
    """Compute ASR confidence from Whisper segment logprobs.

    asr_conf = exp(min(avg_logprob, 0.0)) in (0, 1]
    if no_speech_prob > 0.6: asr_conf *= 0.3
    """
    asr_conf = math.exp(min(avg_logprob, 0.0))
    if no_speech_prob > 0.6:
        asr_conf *= 0.3
    return asr_conf


def aggregate_segments_confidence(segments: Sequence[ASRSegment]) -> float:
    """Compute overall ASR confidence across all segments.

    Weights segment avg_logprob by segment duration and uses max no_speech_prob.
    If segments sequence is empty, returns 1.0.
    """
    if not segments:
        return 1.0

    total_duration = 0.0
    weighted_logprob_sum = 0.0
    max_no_speech = 0.0

    for seg in segments:
        duration = max(0.001, seg.end - seg.start)
        total_duration += duration
        weighted_logprob_sum += seg.avg_logprob * duration
        max_no_speech = max(max_no_speech, seg.no_speech_prob)

    if total_duration <= 0.0:
        return 1.0

    avg_logprob = weighted_logprob_sum / total_duration
    return compute_asr_confidence(avg_logprob, max_no_speech)
