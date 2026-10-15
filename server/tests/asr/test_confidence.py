"""Tests for ASR confidence calculation and aggregation.

Completely offline and deterministic.
"""

from __future__ import annotations

import math
from app.asr.confidence import aggregate_segments_confidence, compute_asr_confidence
from app.schemas import ASRSegment


def test_compute_asr_confidence() -> None:
    # 0.0 logprob -> 1.0 confidence
    assert compute_asr_confidence(0.0, 0.0) == 1.0

    # Positive logprob clamped to 0.0 -> 1.0
    assert compute_asr_confidence(0.5, 0.0) == 1.0

    # Negative logprob
    assert math.isclose(compute_asr_confidence(-0.5, 0.0), math.exp(-0.5))

    # High no-speech probability (> 0.6) penalty: multiplied by 0.3
    penalized = compute_asr_confidence(0.0, 0.65)
    assert math.isclose(penalized, 0.3)

    # Low no-speech probability (<= 0.6): no penalty
    unpenalized = compute_asr_confidence(0.0, 0.59)
    assert unpenalized == 1.0


def test_aggregate_segments_confidence_empty() -> None:
    assert aggregate_segments_confidence([]) == 1.0


def test_aggregate_segments_confidence_multi() -> None:
    seg1 = ASRSegment(
        text="احمد بھائی",
        start=0.0,
        end=1.0,  # duration 1.0
        avg_logprob=-0.2,
        no_speech_prob=0.1,
    )
    seg2 = ASRSegment(
        text="دو کلو چینی",
        start=1.0,
        end=4.0,  # duration 3.0
        avg_logprob=-0.6,
        no_speech_prob=0.2,
    )
    # Expected weighted logprob: (-0.2 * 1.0 + -0.6 * 3.0) / 4.0 = (-0.2 - 1.8) / 4 = -2.0 / 4 = -0.5
    expected_conf = math.exp(-0.5)
    conf = aggregate_segments_confidence([seg1, seg2])
    assert math.isclose(conf, expected_conf, rel_tol=1e-5)


def test_aggregate_segments_confidence_penalized() -> None:
    seg = ASRSegment(
        text="کچھ نہیں",
        start=0.0,
        end=2.0,
        avg_logprob=-0.1,
        no_speech_prob=0.8,  # > 0.6 triggers 0.3 penalty
    )
    conf = aggregate_segments_confidence([seg])
    assert math.isclose(conf, math.exp(-0.1) * 0.3, rel_tol=1e-5)
