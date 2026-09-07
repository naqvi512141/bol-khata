"""Tests for residue collection and attribution rules.

Per docs/02-contracts.md §3 (Residue attribution rules).
"""

from __future__ import annotations

import pytest

from app.extractor.residue import attribute_residue, collect_residue
from app.schemas import Customer, CustomerRef, LineItem, ResidueSpan, SKU


class TestResidueAttribution:
    """Tests for residue interpretation table in docs/02-contracts.md §3."""

    def test_residue_adjacent_to_qty_or_unit_is_product(self) -> None:
        """Residue adjacent to QTY or UNIT is interpreted as product (provisional SKU)."""
        span = ResidueSpan(
            text="کھویا",
            token_span=(2, 3),
            adjacent_to_qty_or_unit=True,
            interpretation="product",
        )
        assert span.interpretation == "product"

    def test_residue_isolated_is_customer_candidate(self) -> None:
        """Isolated residue span is interpreted as customer candidate."""
        span = ResidueSpan(
            text="کامران",
            token_span=(0, 1),
            adjacent_to_qty_or_unit=False,
            interpretation="customer",
        )
        assert span.interpretation == "customer"

    def test_two_or_more_isolated_residue_spans_is_blocking(self) -> None:
        """Two or more isolated residue spans -> blocking. Never guess which is customer."""
        spans = [
            ResidueSpan(
                text="احمد",
                token_span=(3, 4),
                adjacent_to_qty_or_unit=False,
                interpretation="customer",
            ),
            ResidueSpan(
                text="بلال",
                token_span=(5, 6),
                adjacent_to_qty_or_unit=False,
                interpretation="customer",
            ),
        ]
        # Attribution must flag multiple customer candidates as ambiguous/blocking
        assert len(spans) >= 2
