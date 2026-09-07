"""Tests for Catalogue class and price history tracking.

Docs: docs/02-contracts.md §6, §7; docs/03-build-plan.md Phase 4.
"""

from pathlib import Path

import pytest

from app.pricing.catalogue import Catalogue
from app.schemas import SKU

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture
def empty_catalogue() -> Catalogue:
    return Catalogue([])


@pytest.fixture
def sample_catalogue() -> Catalogue:
    skus = [
        SKU(
            sku_id="SKU_001",
            display_name="چینی",
            aliases=["cheeni", "sugar"],
            default_unit="kg",
            unit_price=180,
            max_plausible_qty=25.0,
        ),
        SKU(
            sku_id="SKU_002",
            display_name="آٹا",
            aliases=["aata", "flour"],
            default_unit="kg",
            unit_price=140,
            max_plausible_qty=50.0,
        ),
        SKU(
            sku_id="SKU_003",
            display_name="انڈے",
            aliases=["anday", "eggs"],
            default_unit="dozen",
            unit_price=None,  # missing price in catalogue
            max_plausible_qty=10.0,
        ),
    ]
    return Catalogue(skus)


def test_load_catalogue_from_json() -> None:
    """Catalogue loads cleanly from server/data/catalogue.json."""
    cat_path = DATA_DIR / "catalogue.json"
    cat = Catalogue.from_json(cat_path)
    assert len(cat.skus) == 40
    cheeni = cat.get_sku("SKU_001")
    assert cheeni is not None
    assert cheeni.display_name == "چینی"
    assert cat.current_price("SKU_001") == 180
    assert isinstance(cat.current_price("SKU_001"), int)  # Rule 1: money is int


def test_current_price_missing_or_unknown(sample_catalogue: Catalogue) -> None:
    """current_price returns None for unknown SKU or SKU without unit_price."""
    assert sample_catalogue.current_price("SKU_001") == 180
    assert sample_catalogue.current_price("SKU_003") is None
    assert sample_catalogue.current_price("UNKNOWN_SKU") is None
    assert sample_catalogue.current_price(None) is None


def test_observe_price_and_median(sample_catalogue: Catalogue) -> None:
    """observe_price appends to price_history and median_price computes the median."""
    sku_id = "SKU_001"

    # Fewer than 3 observations: median_price must return None (docs/02 §7)
    assert sample_catalogue.median_price(sku_id) is None

    sample_catalogue.observe_price(sku_id, amount=360, qty=2.0)  # unit price: 180
    assert sample_catalogue.median_price(sku_id) is None

    sample_catalogue.observe_price(sku_id, amount=190, qty=1.0)  # unit price: 190
    assert sample_catalogue.median_price(sku_id) is None

    # 3 observations: median of [180, 190, 185] is 185
    sample_catalogue.observe_price(sku_id, amount=185, qty=1.0)
    med = sample_catalogue.median_price(sku_id)
    assert med == 185
    assert isinstance(med, int)  # AGENTS.md rule 1: money is int


def test_median_price_last_10_window(sample_catalogue: Catalogue) -> None:
    """median_price uses the median of the last 10 entries only."""
    sku_id = "SKU_002"

    # Add 5 old entries at 100
    for _ in range(5):
        sample_catalogue.observe_price(sku_id, amount=100, qty=1.0)

    # Add 10 newer entries at 200
    for _ in range(10):
        sample_catalogue.observe_price(sku_id, amount=200, qty=1.0)

    # Window of last 10 should all be 200 -> median 200
    assert sample_catalogue.median_price(sku_id) == 200


def test_observe_price_unit_price_computation(sample_catalogue: Catalogue) -> None:
    """observe_price computes unit price correctly with fractional qty and rounds to int."""
    sku_id = "SKU_001"

    # 0.5 kg for 95 PKR -> unit price round(95 / 0.5) = 190
    sample_catalogue.observe_price(sku_id, amount=95, qty=0.5)
    sku = sample_catalogue.get_sku(sku_id)
    assert sku is not None
    assert len(sku.price_history) == 1
    assert sku.price_history[0].price == 190
    assert isinstance(sku.price_history[0].price, int)
