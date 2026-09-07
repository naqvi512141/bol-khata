"""Confidence composition for draft transactions.

Docs: docs/02-contracts.md §5.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.schemas import CustomerRef, LineItem, OrderForm

ORDER_PENALTY: dict[OrderForm, float] = {
    "canonical": 1.00,
    "name_last": 0.92,
    "name_medial": 0.88,
    "no_name_draft": 0.95,
    "no_name_cash": 0.85,
}

PRICE_SOURCE_SCORE: dict[str, float] = {
    "spoken": 1.0,
    "catalogue": 0.8,
    "missing": 0.0,
}


def compute_asr_confidence(avg_logprob: float, no_speech_prob: float = 0.0) -> float:
    """Compute ASR confidence from whisper segment logprobs.

    asr_conf = exp(min(avg_logprob, 0.0)) in (0, 1]
    if no_speech_prob > 0.6: asr_conf *= 0.3
    """
    asr_conf = math.exp(min(avg_logprob, 0.0))
    if no_speech_prob > 0.6:
        asr_conf *= 0.3
    return asr_conf


def compute_confidence(
    items: Sequence[LineItem],
    customer: CustomerRef,
    order_form: OrderForm,
    validation_passed: bool,
    asr_conf: float = 1.0,
) -> float:
    """Compose overall transaction confidence score per docs/02 §5.

    Formula:
      confidence = (
          0.35 * asr_conf
        + 0.20 * min([i.match_score for i in items] or [0.0])
        + 0.20 * customer_conf
        + 0.10 * price_source_score[worst_price_source]
        + 0.15 * (1.0 if validation.passed else 0.0)
      ) * ORDER_PENALTY[order_form]
    """
    # Min SKU match score (default 0.0 if no items)
    min_sku_score = min([i.match_score for i in items] or [0.0])

    # Customer confidence
    customer_conf = customer.confidence

    # Price source score: worst across items
    if items:
        worst_price_source_score = min(
            PRICE_SOURCE_SCORE.get(i.price_source, 0.0) for i in items
        )
    else:
        worst_price_source_score = 0.0

    val_score = 1.0 if validation_passed else 0.0

    raw_conf = (
        0.35 * asr_conf
        + 0.20 * min_sku_score
        + 0.20 * customer_conf
        + 0.10 * worst_price_source_score
        + 0.15 * val_score
    )

    penalty = ORDER_PENALTY.get(order_form, 1.0)
    final_conf = raw_conf * penalty
    return max(0.0, min(1.0, round(final_conf, 4)))
