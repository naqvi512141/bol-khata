"""
tests/normalizer/test_lexicons.py
Tests for app/normalizer/lexicons.py

Expected values are authoritative — from docs/01-domain-urdu.md §6.
Do not change expected values to make the implementation pass.
"""
from __future__ import annotations

from app.normalizer.lexicons import (
    HONORIFICS,
    GENITIVE_MARKERS,
    FILLERS,
    NEGATION,
    UDHAAR_MARKERS,
    CASH_MARKERS,
    CURRENCY,
    QUERY_MARKERS,
)


class TestLexiconMembership:
    """
    Spot-check every list from docs/01 §6 for required members.
    The complete set is in the data; we test a representative subset
    to confirm the data is loaded correctly.
    """

    # HONORIFICS — docs/01 §6
    def test_bhai_in_honorifics(self) -> None:
        assert "بھائی" in HONORIFICS

    def test_sahib_in_honorifics(self) -> None:
        assert "صاحب" in HONORIFICS

    def test_ji_in_honorifics(self) -> None:
        assert "جی" in HONORIFICS

    def test_baji_in_honorifics(self) -> None:
        assert "باجی" in HONORIFICS

    def test_khala_in_honorifics(self) -> None:
        assert "خالہ" in HONORIFICS

    def test_chacha_in_honorifics(self) -> None:
        assert "چاچا" in HONORIFICS

    def test_uncle_in_honorifics(self) -> None:
        assert "انکل" in HONORIFICS

    def test_aapa_in_honorifics(self) -> None:
        assert "آپا" in HONORIFICS

    # GENITIVE_MARKERS — docs/01 §6
    def test_ka_in_genitive(self) -> None:
        assert "کا" in GENITIVE_MARKERS

    def test_ki_in_genitive(self) -> None:
        assert "کی" in GENITIVE_MARKERS

    def test_ke_in_genitive(self) -> None:
        assert "کے" in GENITIVE_MARKERS

    # FILLERS — docs/01 §6
    def test_achha_in_fillers(self) -> None:
        assert "اچھا" in FILLERS

    def test_theek_in_fillers(self) -> None:
        assert "ٹھیک" in FILLERS

    def test_aur_in_fillers(self) -> None:
        assert "اور" in FILLERS

    # NEGATION — docs/01 §6
    def test_nahin_in_negation(self) -> None:
        assert "نہیں" in NEGATION

    def test_ghalat_in_negation(self) -> None:
        assert "غلط" in NEGATION

    def test_ruko_in_negation(self) -> None:
        assert "رکو" in NEGATION

    # UDHAAR_MARKERS — docs/01 §6
    def test_udhaar_urdu_in_udhaar_markers(self) -> None:
        assert "ادھار" in UDHAAR_MARKERS

    def test_khata_urdu_in_udhaar_markers(self) -> None:
        assert "خاتہ" in UDHAAR_MARKERS

    def test_udhaar_roman_in_udhaar_markers(self) -> None:
        assert "udhaar" in UDHAAR_MARKERS

    # CASH_MARKERS — docs/01 §6
    def test_naqd_in_cash_markers(self) -> None:
        assert "نقد" in CASH_MARKERS

    def test_cash_roman_in_cash_markers(self) -> None:
        assert "cash" in CASH_MARKERS

    # CURRENCY — docs/01 §6
    def test_rupay_in_currency(self) -> None:
        assert "روپے" in CURRENCY

    def test_pkr_in_currency(self) -> None:
        assert "PKR" in CURRENCY

    def test_rs_in_currency(self) -> None:
        assert "Rs" in CURRENCY

    # QUERY_MARKERS — docs/01 §6
    def test_balance_urdu_in_query_markers(self) -> None:
        assert "بیلنس" in QUERY_MARKERS

    def test_balance_roman_in_query_markers(self) -> None:
        assert "balance" in QUERY_MARKERS


class TestLexiconTypes:
    """All lexicons must be lists (data, not sets) so they can be ordered/iterated."""

    def test_honorifics_is_list(self) -> None:
        assert isinstance(HONORIFICS, list)

    def test_genitive_markers_is_list(self) -> None:
        assert isinstance(GENITIVE_MARKERS, list)

    def test_fillers_is_list(self) -> None:
        assert isinstance(FILLERS, list)

    def test_negation_is_list(self) -> None:
        assert isinstance(NEGATION, list)

    def test_udhaar_markers_is_list(self) -> None:
        assert isinstance(UDHAAR_MARKERS, list)

    def test_cash_markers_is_list(self) -> None:
        assert isinstance(CASH_MARKERS, list)

    def test_currency_is_list(self) -> None:
        assert isinstance(CURRENCY, list)

    def test_query_markers_is_list(self) -> None:
        assert isinstance(QUERY_MARKERS, list)
