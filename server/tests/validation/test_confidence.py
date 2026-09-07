"""Tests for confidence composition per docs/02-contracts.md §5."""

import math

import pytest

from app.schemas import CustomerRef, LineItem
from app.validation.confidence import compute_asr_confidence, compute_confidence


def test_asr_confidence() -> None:
    """compute_asr_confidence computes exp(min(avg_logprob, 0.0)) and applies no_speech_prob penalty."""
    # Perfect logprob 0.0 -> conf 1.0
    assert compute_asr_confidence(0.0, 0.0) == 1.0

    # Negative logprob
    conf = compute_asr_confidence(-0.5, 0.1)
    assert pytest.approx(conf, 0.001) == math.exp(-0.5)

    # High no_speech_prob > 0.6 cuts confidence by 70% (* 0.3)
    penalized = compute_asr_confidence(0.0, 0.8)
    assert pytest.approx(penalized, 0.001) == 0.3


def test_confidence_clean_canonical() -> None:
    """Confidence is high for clean input in canonical order."""
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        qty=1.0,
        price_source="spoken",
        match_score=1.0,
        match_status="resolved",
        token_span=(0, 2),
    )
    customer = CustomerRef(status="resolved", confidence=1.0, source="spoken")

    # All components 1.0:
    # 0.35 * 1.0 (asr) + 0.20 * 1.0 (sku) + 0.20 * 1.0 (cust) + 0.10 * 1.0 (price) + 0.15 * 1.0 (val) = 1.0
    # Penalty for canonical is 1.0 -> 1.0
    conf = compute_confidence(
        items=[item],
        customer=customer,
        order_form="canonical",
        validation_passed=True,
        asr_conf=1.0,
    )
    assert conf == 1.0


def test_confidence_order_penalties() -> None:
    """Order penalties reduce overall confidence."""
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        qty=1.0,
        price_source="spoken",
        match_score=1.0,
        match_status="resolved",
        token_span=(0, 2),
    )
    customer = CustomerRef(status="resolved", confidence=1.0, source="spoken")

    conf_last = compute_confidence(
        items=[item],
        customer=customer,
        order_form="name_last",
        validation_passed=True,
        asr_conf=1.0,
    )
    # 1.0 * 0.92 = 0.92
    assert conf_last == 0.92

    conf_cash = compute_confidence(
        items=[item],
        customer=CustomerRef(status="absent", confidence=0.0, source="cash_default"),
        order_form="no_name_cash",
        validation_passed=True,
        asr_conf=1.0,
    )
    # (0.35 + 0.20 + 0.0 + 0.10 + 0.15) * 0.85 = 0.80 * 0.85 = 0.68
    assert pytest.approx(conf_cash, 0.001) == 0.68
