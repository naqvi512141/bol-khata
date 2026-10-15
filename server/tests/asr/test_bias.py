"""Tests for bias prompt builder and token cap assertion.

Offline and deterministic.
"""

from __future__ import annotations

from app.asr.bias import build_bias_prompt, estimate_token_count
from app.schemas import Customer, SKU


def test_bias_prompt_default() -> None:
    """Default bias prompt contains numerals, customer names, and SKUs."""
    prompt = build_bias_prompt()
    assert len(prompt) > 0

    # Must contain anchor numerals and commercial words
    assert "ایک" in prompt
    assert "روپے" in prompt
    assert "کلو" in prompt

    # Must stay strictly under 200 tokens
    tokens = estimate_token_count(prompt)
    assert tokens <= 200, f"Prompt token count {tokens} exceeds cap 200"


def test_bias_prompt_token_cap_with_huge_dataset() -> None:
    """Even with hundreds of SKUs and customers, the prompt stays <= 200 tokens."""
    massive_catalogue = [
        SKU(
            sku_id=f"SKU_{i:03d}",
            display_name=f"پروڈکٹ {i}",
            aliases=[f"alias_{i}"],
            default_unit="kg",
            unit_price=100 + i,
        )
        for i in range(200)
    ]
    massive_customers = [
        Customer(
            customer_id=f"CUST_{i:03d}",
            display_name=f"کسٹمر {i}",
            aliases=[f"alias_cust_{i}"],
            balance=1000 + i,
        )
        for i in range(100)
    ]

    prompt = build_bias_prompt(
        catalogue=massive_catalogue,
        customers=massive_customers,
        max_tokens=200,
    )
    tokens = estimate_token_count(prompt)
    assert tokens <= 200, f"Estimated tokens {tokens} exceeds cap 200"
    assert len(prompt) > 0


def test_bias_prompt_strict_custom_cap() -> None:
    """Prompt respects smaller custom caps like 80 tokens."""
    prompt = build_bias_prompt(max_tokens=80)
    tokens = estimate_token_count(prompt)
    assert tokens <= 80, f"Estimated tokens {tokens} exceeds cap 80"


def test_estimate_token_count() -> None:
    assert estimate_token_count("") == 0
    assert estimate_token_count("   ") == 0
    # Single Urdu word
    urdu_tokens = estimate_token_count("چینی")
    assert urdu_tokens >= 2
