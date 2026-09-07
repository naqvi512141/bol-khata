"""
tests/normalizer/test_units.py
Tests for app/normalizer/units.py

Expected values are authoritative — from docs/01-domain-urdu.md §5 and §8.
Do not change expected values to make the implementation pass.
"""
from __future__ import annotations

import pytest

from app.normalizer.units import resolve_unit, disambiguate_paw


# ---------------------------------------------------------------------------
# §5 — UNITS_CANON basic resolution
# ---------------------------------------------------------------------------

class TestUnitResolution:
    """
    Each Urdu unit token must resolve to its canonical (unit_code, factor) pair.
    Expected from docs/01 §5 UNITS_CANON table.
    """

    def test_kilo(self) -> None:
        code, factor = resolve_unit("کلو")
        assert code == "kg"
        assert factor == pytest.approx(1.0)

    def test_kilogram(self) -> None:
        code, factor = resolve_unit("کلوگرام")
        assert code == "kg"
        assert factor == pytest.approx(1.0)

    def test_gram(self) -> None:
        code, factor = resolve_unit("گرام")
        assert code == "g"
        assert factor == pytest.approx(1.0)

    def test_seer(self) -> None:
        code, factor = resolve_unit("سیر")
        assert code == "kg"
        assert factor == pytest.approx(0.933)

    def test_chhataank(self) -> None:
        code, factor = resolve_unit("چھٹانک")
        assert code == "g"
        assert factor == pytest.approx(58.3)

    def test_darjan(self) -> None:
        code, factor = resolve_unit("درجن")
        assert code == "dozen"
        assert factor == pytest.approx(12.0)

    def test_litre(self) -> None:
        code, factor = resolve_unit("لیٹر")
        assert code == "l"
        assert factor == pytest.approx(1.0)

    def test_bottle(self) -> None:
        code, factor = resolve_unit("بوتل")
        assert code == "bottle"
        assert factor == pytest.approx(1.0)

    def test_packet(self) -> None:
        code, factor = resolve_unit("پیکٹ")
        assert code == "packet"
        assert factor == pytest.approx(1.0)

    def test_dabba(self) -> None:
        code, factor = resolve_unit("ڈبہ")
        assert code == "box"
        assert factor == pytest.approx(1.0)

    def test_unknown_token_returns_none(self) -> None:
        assert resolve_unit("بلبل") is None


# ---------------------------------------------------------------------------
# §5 — paw disambiguation (docs/01 §5 "paw disambiguation — fully specified")
# ---------------------------------------------------------------------------

class TestPawDisambiguation:
    """
    Four exhaustive cases defined in docs/01 §5.
    All four must behave exactly as specified.
    """

    def test_paw_before_unit_is_quantifier(self) -> None:
        # Case 1: next token is a unit -> paw is a quantifier: 0.25 × that unit
        # "paw kilo" -> qty=0.25, unit=kg  (docs/01 §8)
        result = disambiguate_paw(next_token="کلو", sku_default_unit=None)
        assert result["role"] == "quantifier"
        assert result["qty"] == pytest.approx(0.25)
        assert result["unit"] == "kg"

    def test_paw_before_item_is_unit(self) -> None:
        # Case 2: next token is an item -> paw is the unit itself (250 g = 0.25 kg)
        # "paw cheeni" -> qty=0.25, unit=kg  (docs/01 §8)
        result = disambiguate_paw(next_token=None, sku_default_unit="kg")
        assert result["role"] == "unit"
        assert result["qty"] == pytest.approx(0.25)
        assert result["unit"] == "kg"

    def test_paw_alone_defaults_to_0_25_kg(self) -> None:
        # Case 3: paw stands alone (no following token) -> 0.25 kg
        result = disambiguate_paw(next_token=None, sku_default_unit=None)
        assert result["role"] == "unit"
        assert result["qty"] == pytest.approx(0.25)
        assert result["unit"] == "kg"

    def test_paw_with_non_mass_sku_is_blocking(self) -> None:
        # Case 4: SKU default_unit is not kg or g -> ambiguous -> blocking
        # "paw bottle" is not a real quantity (docs/01 §5 + §8)
        result = disambiguate_paw(next_token=None, sku_default_unit="bottle")
        assert result["role"] == "blocking"
