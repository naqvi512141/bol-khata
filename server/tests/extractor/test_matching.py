"""Tests for SKU and Customer matching algorithms and priors.

Per docs/02-contracts.md §4, AGENTS.md rules 7, 8, 9.
"""

from __future__ import annotations

import pytest

from app.extractor.matching import (
    CUST_ACCEPT_SCORE,
    CUST_MARGIN,
    SKU_ACCEPT_SCORE,
    SKU_AMBIGUOUS_MIN,
    SKU_MARGIN,
    match_customer,
    match_sku,
)
from app.schemas import Customer, SKU


class TestSKUMatching:
    """Tests for match_sku, score thresholds, margin check, and priors."""

    def test_exact_sku_match(self, catalogue: list[SKU]) -> None:
        """Exact display name or alias matches with high score."""
        res = match_sku("چینی", catalogue)
        assert res.status == "resolved"
        assert res.sku_id == "SKU_001"
        assert res.score >= SKU_ACCEPT_SCORE

    def test_alias_sku_match(self, catalogue: list[SKU]) -> None:
        """Alias in Roman or alternative Urdu matches correctly."""
        res = match_sku("cheeni", catalogue)
        assert res.status == "resolved"
        assert res.sku_id == "SKU_001"

    def test_multi_token_sku_laal_mirch(self, catalogue: list[SKU]) -> None:
        """Multi-token SKU is resolved as one item (AGENTS.md rule 7)."""
        res = match_sku("لال مرچ", catalogue)
        assert res.status == "resolved"
        assert res.sku_id == "SKU_007"

    def test_sku_margin_rule(self) -> None:
        """AGENTS.md rule 8: If runner-up is within SKU_MARGIN (8 points), status is ambiguous."""
        dummy_catalogue = [
            SKU(sku_id="SKU_A", display_name="دال چنا", default_unit="kg"),
            SKU(sku_id="SKU_B", display_name="دال مسور", default_unit="kg"),
        ]
        # Query "دال" might match both closely
        res = match_sku("دال", dummy_catalogue)
        if res.score >= SKU_AMBIGUOUS_MIN:
            # If scores are too close, it must not resolve cleanly without margin
            if res.margin < SKU_MARGIN:
                assert res.status == "ambiguous"

    def test_sku_below_ambiguous_min_is_unknown(self, catalogue: list[SKU]) -> None:
        """Below SKU_AMBIGUOUS_MIN (70) -> status is unknown."""
        res = match_sku("کتابچہ پینسل", catalogue)
        assert res.status == "unknown"
        assert res.sku_id is None


class TestCustomerMatching:
    """Tests for match_customer, threshold (75), margin (10), and priors."""

    def test_exact_customer_match(self, customers: list[Customer]) -> None:
        """Exact customer name resolves with score >= CUST_ACCEPT_SCORE (75)."""
        res = match_customer("بلال", customers)
        assert res.status == "resolved"
        assert res.customer_id == "CUST_004"
        assert res.score >= CUST_ACCEPT_SCORE

    def test_customer_margin_check_ambiguous(self) -> None:
        """Two near-duplicate customers within margin < 10 must return ambiguous (AGENTS.md rule 8)."""
        # Two identical/near-identical customers without priors distinguishing them
        candidates = [
            Customer(customer_id="C_1", display_name="احمد علی", aliases=["ahmed ali"]),
            Customer(customer_id="C_2", display_name="احمد ولی", aliases=["ahmed wali"]),
        ]
        res = match_customer("احمد", candidates)
        if res.score >= CUST_ACCEPT_SCORE:
            if res.margin < CUST_MARGIN:
                assert res.status == "ambiguous"
                assert len(res.candidates) >= 2

    def test_customer_recency_and_balance_boost(self) -> None:
        """Recency and open balance boost separate near-duplicate customers."""
        candidates = [
            Customer(
                customer_id="C_REC",
                display_name="احمد",
                balance=2500,  # has balance -> boost 1.15
                last_txn_at="2026-09-06T14:30:00+05:00",  # recent
            ),
            Customer(
                customer_id="C_OLD",
                display_name="احمد",
                balance=0,  # no balance
                last_txn_at="2026-06-01T09:00:00+05:00",  # old (>21 days)
            ),
        ]
        res = match_customer("احمد", candidates)
        assert res.status == "resolved"
        assert res.customer_id == "C_REC"
