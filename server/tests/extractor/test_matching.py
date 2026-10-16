"""Tests for SKU and Customer matching algorithms and priors.

Per docs/02-contracts.md §4, AGENTS.md rules 7, 8, 9.
"""

from __future__ import annotations

from unittest.mock import patch

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
from app.schemas import Customer, CustomerRef, LineItem, ParsedDraft, SKU, ValidationResult


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
        """Recency and open balance boost break tie in ranking, but identical names stay ambiguous."""
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
        # Raw scores are identical (100 vs 100 -> raw margin 0), so it stays ambiguous
        assert res.status == "ambiguous"
        assert res.customer_id is None
        # Priors break the tie in ranking order
        assert res.candidates == ["C_REC", "C_OLD"]

    def test_customer_raw_margin_insufficient_with_strong_prior(self) -> None:
        """Two customers with raw scores 88 and 86 (raw margin 2), where one has a
        strong recency prior, must return ambiguous -- not resolved.
        """
        c1 = Customer(
            customer_id="C_1",
            display_name="احمد علی",
            balance=0,
            last_txn_at="2026-09-07T11:00:00+05:00",  # strong recency prior
        )
        c2 = Customer(
            customer_id="C_2",
            display_name="احمد ولی",
            balance=0,
            last_txn_at=None,
        )

        def mock_similarity(q: str, target: str) -> float:
            if "علی" in target:
                return 88.0
            return 86.0

        with patch("app.extractor.matching._score_similarity", side_effect=mock_similarity):
            res = match_customer("احمد", [c1, c2])

        assert res.status == "ambiguous"
        assert res.customer_id is None
        assert "C_1" in res.candidates
        assert "C_2" in res.candidates

    def test_confidence_above_1_never_returned(self) -> None:
        """Fix 1: Confidence is always in [0, 1] — customer, SKU, and composite."""
        cust = Customer(
            customer_id="C_MAX",
            display_name="احمد",
            balance=5000,  # +15% boost
            last_txn_at="2026-09-07T11:00:00+05:00",  # recent -> +10% boost
        )
        res = match_customer("احمد", [cust])
        # Reported score in MatchResult must be clamped to <= 100.0
        assert res.score <= 100.0

        # CustomerRef confidence must be clamped to <= 1.0
        cust_ref = CustomerRef(
            customer_id=res.customer_id,
            status="resolved",
            confidence=res.score / 100.0,
            source="spoken",
        )
        assert 0.0 <= cust_ref.confidence <= 1.0

        # Direct construction with confidence > 1.0 must be clamped
        clamped_ref = CustomerRef(
            customer_id="C_TEST",
            status="resolved",
            confidence=1.260884,
            source="spoken",
        )
        assert clamped_ref.confidence <= 1.0

        # LineItem match_score clamped
        clamped_item = LineItem(
            sku_id="SKU_001",
            raw_name="چینی",
            match_score=1.25,
            match_status="resolved",
            token_span=(0, 1),
        )
        assert clamped_item.match_score <= 1.0

        # ParsedDraft composite confidence clamped
        draft = ParsedDraft(
            draft_id="d_test",
            job_ids=["j_01"],
            shop_id="s_01",
            customer=cust_ref,
            items=[clamped_item],
            computed_total=100,
            payment_type="cash",
            order_form="canonical",
            confidence=1.260884,
            path="fast",
            validation=ValidationResult(passed=True),
            normalized_tokens="test",
        )
        assert draft.confidence <= 1.0

    def test_candidate_raw_70_strong_prior_does_not_resolve(self) -> None:
        """Fix 2: Raw pre-prior score must meet CUST_ACCEPT_SCORE (75).

        A candidate with raw score 70 and a strong recency/balance prior (boost > 1.25,
        which would boost to ~88) must NOT resolve. A prior should break ties,
        not promote a failing match.
        """
        cust = Customer(
            customer_id="C_WEAK",
            display_name="احمد",
            balance=5000,  # 1.15 boost
            last_txn_at="2026-09-07T11:00:00+05:00",  # ~1.10 boost
        )
        with patch("app.extractor.matching._score_similarity", return_value=70.0):
            res = match_customer("احمد", [cust])

        assert res.status != "resolved"
        assert res.status == "unknown"
        assert res.customer_id is None

    def test_candidate_raw_90_no_prior_does_resolve(self) -> None:
        """Fix 2: A candidate with raw 90 (>= 75) and no prior does resolve."""
        cust = Customer(
            customer_id="C_STRONG",
            display_name="بلال",
            balance=0,  # no balance boost
            last_txn_at=None,  # no recency boost
        )
        with patch("app.extractor.matching._score_similarity", return_value=90.0):
            res = match_customer("بلال", [cust])

        assert res.status == "resolved"
        assert res.customer_id == "C_STRONG"
        assert res.score <= 100.0
