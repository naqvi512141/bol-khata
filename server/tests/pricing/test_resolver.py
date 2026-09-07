"""Tests for three-tier price resolver.

Rules:
- Price priority is exactly: spoken > catalogue lookup > missing. (docs/02-contracts.md §6)
- No float in money path; round once at computation and store. (AGENTS.md rule 1)
"""

import pytest

from app.pricing.catalogue import Catalogue
from app.pricing.resolver import resolve_price, resolve_prices
from app.schemas import SKU, LineItem


@pytest.fixture
def catalogue() -> Catalogue:
    skus = [
        SKU(
            sku_id="SKU_001",
            display_name="چینی",
            aliases=["cheeni"],
            default_unit="kg",
            unit_price=180,
        ),
        SKU(
            sku_id="SKU_002",
            display_name="آٹا",
            aliases=["aata"],
            default_unit="kg",
            unit_price=140,
        ),
        SKU(
            sku_id="SKU_003",
            display_name="انڈے",
            aliases=["anday"],
            default_unit="dozen",
            unit_price=None,  # No catalogue price
        ),
    ]
    return Catalogue(skus)


def test_priority_spoken_over_catalogue(catalogue: Catalogue) -> None:
    """Spoken amount takes precedence even when catalogue price exists."""
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        qty=2.0,
        unit="kg",
        spoken_amount=350,  # Spoken discounted amount
        unit_price=None,
        match_status="resolved",
        token_span=(0, 2),
    )

    resolved = resolve_price(item, catalogue)

    assert resolved.price_source == "spoken"
    assert resolved.line_total == 350
    assert isinstance(resolved.line_total, int)
    # Spoken observation recorded into catalogue price_history
    sku = catalogue.get_sku("SKU_001")
    assert sku is not None
    assert len(sku.price_history) == 1
    assert sku.price_history[0].price == 175  # 350 / 2.0


def test_priority_catalogue_lookup(catalogue: Catalogue) -> None:
    """When spoken_amount is None, unit_price and line_total come from catalogue."""
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        qty=2.5,
        unit="kg",
        spoken_amount=None,
        unit_price=None,
        match_status="resolved",
        token_span=(0, 2),
    )

    resolved = resolve_price(item, catalogue)

    assert resolved.price_source == "catalogue"
    assert resolved.unit_price == 180
    assert resolved.line_total == 450  # round(180 * 2.5) = 450
    assert isinstance(resolved.line_total, int)
    assert "line_total" in resolved.derived_fields


def test_priority_missing_when_not_in_catalogue(catalogue: Catalogue) -> None:
    """When spoken_amount is None and SKU has no catalogue price, source is 'missing'."""
    item = LineItem(
        sku_id="SKU_003",
        raw_name="انڈے",
        qty=1.0,
        unit="dozen",
        spoken_amount=None,
        unit_price=None,
        match_status="resolved",
        token_span=(0, 2),
    )

    resolved = resolve_price(item, catalogue)

    assert resolved.price_source == "missing"
    assert resolved.line_total is None


def test_priority_missing_when_unknown_sku(catalogue: Catalogue) -> None:
    """When SKU is not in catalogue at all and no spoken amount, source is 'missing'."""
    item = LineItem(
        sku_id=None,
        raw_name="کچھ نیا",
        qty=1.0,
        unit="piece",
        spoken_amount=None,
        match_status="unknown",
        token_span=(0, 2),
    )

    resolved = resolve_price(item, catalogue)

    assert resolved.price_source == "missing"
    assert resolved.line_total is None


def test_resolve_prices_batch(catalogue: Catalogue) -> None:
    """resolve_prices processes all items in order."""
    items = [
        LineItem(
            sku_id="SKU_001",
            raw_name="چینی",
            qty=1.0,
            unit="kg",
            spoken_amount=200,
            match_status="resolved",
            token_span=(0, 2),
        ),
        LineItem(
            sku_id="SKU_002",
            raw_name="آٹا",
            qty=3.0,
            unit="kg",
            spoken_amount=None,
            match_status="resolved",
            token_span=(2, 4),
        ),
    ]

    resolved_items = resolve_prices(items, catalogue)
    assert resolved_items[0].price_source == "spoken"
    assert resolved_items[0].line_total == 200
    assert resolved_items[1].price_source == "catalogue"
    assert resolved_items[1].line_total == 420  # 140 * 3
