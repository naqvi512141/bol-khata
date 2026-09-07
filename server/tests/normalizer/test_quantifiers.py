"""
tests/normalizer/test_quantifiers.py
Tests for app/normalizer/quantifiers.py

Expected values are authoritative — from docs/01-domain-urdu.md §4 and §8.
Do not change expected values to make the implementation pass.

CRITICAL — AGENTS.md rule 3:
    paun (پونے) SUBTRACTS 0.25.
    paun chaar kilo = 3.75, NOT 4.25.
"""
from __future__ import annotations

import pytest

from app.normalizer.quantifiers import resolve_quantifier


# ---------------------------------------------------------------------------
# §4 Class A — Standalone quantifiers
# Standalone values are a complete quantity on their own.
# ---------------------------------------------------------------------------

class TestStandaloneQuantifiers:
    """
    docs/01 §4 Class A table.
    All four standalone words must parse to their exact float values.
    """

    def test_aadha(self) -> None:
        # آدھا (aadha) = 0.5  (docs/01 §4)
        qty, unit_hint = resolve_quantifier(["آدھا"], 0)
        assert qty == pytest.approx(0.5)
        assert unit_hint is None

    def test_paw_standalone(self) -> None:
        # پاؤ (paw) = 0.25  (docs/01 §4)
        # Standalone form — NOT followed by a unit or item token -> 0.25 kg per docs/01 §5
        qty, unit_hint = resolve_quantifier(["پاؤ"], 0)
        assert qty == pytest.approx(0.25)
        assert unit_hint == "kg"

    def test_derh(self) -> None:
        # ڈیڑھ (derh) = 1.5  (docs/01 §4)
        qty, unit_hint = resolve_quantifier(["ڈیڑھ"], 0)
        assert qty == pytest.approx(1.5)
        assert unit_hint is None

    def test_dhai(self) -> None:
        # ڈھائی (dhai) = 2.5  (docs/01 §4)
        qty, unit_hint = resolve_quantifier(["ڈھائی"], 0)
        assert qty == pytest.approx(2.5)
        assert unit_hint is None


# ---------------------------------------------------------------------------
# §4 Class B — Prefix modifiers
# Apply to the number that FOLLOWS. If no following number -> None (blocking).
# ---------------------------------------------------------------------------

class TestModifierQuantifiers:
    """
    docs/01 §4 Class B table, and docs/01 §8 required test cases.
    """

    def test_sawa_teen(self) -> None:
        # سوا تین (sawa teen) = 3 + 0.25 = 3.25  (docs/01 §4 + §8)
        qty, unit_hint = resolve_quantifier(["سوا", "تین"], 0)
        assert qty == pytest.approx(3.25)
        assert unit_hint is None

    def test_saarhe_saat(self) -> None:
        # ساڑھے سات (saarhe saat) = 7 + 0.5 = 7.5  (docs/01 §4 + §8)
        qty, unit_hint = resolve_quantifier(["ساڑھے", "سات"], 0)
        assert qty == pytest.approx(7.5)
        assert unit_hint is None

    def test_paun_chaar(self) -> None:
        # پونے چار (paun chaar) = 4 - 0.25 = 3.75  (docs/01 §4 + §8, AGENTS.md rule 3)
        # THIS SUBTRACTS. 4.25 is WRONG.
        qty, unit_hint = resolve_quantifier(["پونے", "چار"], 0)
        assert qty == pytest.approx(3.75)
        assert unit_hint is None

    def test_paun_is_not_4_25(self) -> None:
        # Explicit guard: paun chaar MUST NOT be 4.25 (AGENTS.md rule 3)
        qty, _ = resolve_quantifier(["پونے", "چار"], 0)
        assert qty != pytest.approx(4.25), "paun SUBTRACTS — 4.25 is wrong"

    def test_sawa_alone_returns_none(self) -> None:
        # docs/01 §4: "dangling modifier ... return None. Do not default."
        # docs/01 §8: sawa alone -> None -> blocking
        qty, unit_hint = resolve_quantifier(["سوا"], 0)
        assert qty is None
        assert unit_hint is None

    def test_saarhe_alone_returns_none(self) -> None:
        # Same rule: dangling modifier returns None
        qty, unit_hint = resolve_quantifier(["ساڑھے"], 0)
        assert qty is None
        assert unit_hint is None

    def test_paun_alone_returns_none(self) -> None:
        # Same rule: dangling modifier returns None
        qty, unit_hint = resolve_quantifier(["پونے"], 0)
        assert qty is None
        assert unit_hint is None


# ---------------------------------------------------------------------------
# §4 + §5 — Integration: quantifier + unit
# These are in the §8 required test cases.
# ---------------------------------------------------------------------------

class TestQuantifierWithUnit:
    """
    docs/01 §8 required test cases that combine a quantifier with a unit token.
    """

    def test_dhai_kilo(self) -> None:
        # ڈھائی کلو (dhai kilo) -> qty=2.5, unit=kg  (docs/01 §8)
        qty, unit_hint = resolve_quantifier(["ڈھائی", "کلو"], 0)
        assert qty == pytest.approx(2.5)
        assert unit_hint == "kg"

    def test_derh_kilo(self) -> None:
        # ڈیڑھ کلو (derh kilo) -> qty=1.5, unit=kg  (docs/01 §8)
        qty, unit_hint = resolve_quantifier(["ڈیڑھ", "کلو"], 0)
        assert qty == pytest.approx(1.5)
        assert unit_hint == "kg"

    def test_aadha_kilo(self) -> None:
        # آدھا کلو (aadha kilo) -> qty=0.5, unit=kg  (docs/01 §8)
        qty, unit_hint = resolve_quantifier(["آدھا", "کلو"], 0)
        assert qty == pytest.approx(0.5)
        assert unit_hint == "kg"

    def test_paun_chaar_kilo(self) -> None:
        # پونے چار کلو (paun chaar kilo) -> qty=3.75, unit=kg  (docs/01 §8 + AGENTS.md rule 3)
        qty, unit_hint = resolve_quantifier(["پونے", "چار", "کلو"], 0)
        assert qty == pytest.approx(3.75)
        assert unit_hint == "kg"
