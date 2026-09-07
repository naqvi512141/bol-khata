"""
tests/normalizer/test_numbers.py
Tests for app/normalizer/numbers.py

Expected values are authoritative — from docs/01-domain-urdu.md §3 and §8.
Do not change expected values to make the implementation pass.
"""
from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Import paths will resolve once the implementation exists.
# ---------------------------------------------------------------------------
from app.normalizer.numbers import parse_number_words
from app.normalizer.folding import urdu_fold


# ---------------------------------------------------------------------------
# §3 — Cardinal completeness
# ---------------------------------------------------------------------------

class TestCardinalTableComplete:
    """
    Every integer 0-99 must appear in the loaded cardinal table.
    Marked xfail because the table has deliberate gaps pending native-speaker
    verification (docs/01-domain-urdu.md §3).
    """

    @pytest.mark.xfail(reason="native-speaker verification pending — cardinal table has intentional gaps")
    def test_cardinal_table_complete(self) -> None:
        from app.normalizer.numbers import CARDINALS
        for i in range(100):
            assert i in CARDINALS.values(), f"Cardinal {i} is missing from the table"


# ---------------------------------------------------------------------------
# §3 — Compound number algorithm (docs/01 §3 examples)
# ---------------------------------------------------------------------------

class TestParseNumberWords:
    """
    Input tokens are already folded Urdu text.
    Expected values from docs/01-domain-urdu.md §3 and §8.
    """

    def test_saat_sau_bees(self) -> None:
        # docs/01 §3 example: saat sau bees -> 720
        tokens = ["سات", "سو", "بیس"]
        assert parse_number_words(tokens) == 720

    def test_do_hazaar_teen_sau_pachaas(self) -> None:
        # docs/01 §8: "do hazaar teen sau pachaas" -> 2350
        tokens = ["دو", "ہزار", "تین", "سو", "پچاس"]
        assert parse_number_words(tokens) == 2350

    def test_single_cardinal_ek(self) -> None:
        tokens = ["ایک"]
        assert parse_number_words(tokens) == 1

    def test_single_cardinal_do(self) -> None:
        tokens = ["دو"]
        assert parse_number_words(tokens) == 2

    def test_single_cardinal_teen(self) -> None:
        tokens = ["تین"]
        assert parse_number_words(tokens) == 3

    def test_single_cardinal_chaar(self) -> None:
        tokens = ["چار"]
        assert parse_number_words(tokens) == 4

    def test_sau_without_leading_cardinal_is_100(self) -> None:
        # "sau" alone with no preceding cardinal -> current is 0, (0 or 1)*100 = 100
        tokens = ["سو"]
        assert parse_number_words(tokens) == 100

    def test_hazaar_without_leading_cardinal_is_1000(self) -> None:
        tokens = ["ہزار"]
        assert parse_number_words(tokens) == 1000

    def test_do_hazaar(self) -> None:
        tokens = ["دو", "ہزار"]
        assert parse_number_words(tokens) == 2000

    def test_stops_at_first_non_number_token(self) -> None:
        # Stops at the first non-number token; docs/01 §3 algorithm
        tokens = ["تین", "سو", "کلو"]
        result = parse_number_words(tokens)
        # "teen sau" parsed before "kilo" -> 300; kilo stops the loop
        assert result == 300

    def test_empty_list_returns_none(self) -> None:
        assert parse_number_words([]) is None

    def test_unknown_token_alone_returns_none(self) -> None:
        # A word that is not in the cardinal or multiplier table
        assert parse_number_words(["کلو"]) is None

    def test_lakh(self) -> None:
        tokens = ["ایک", "لاکھ"]
        assert parse_number_words(tokens) == 100_000

    def test_two_lakh(self) -> None:
        tokens = ["دو", "لاکھ"]
        assert parse_number_words(tokens) == 200_000

    def test_chhe_alias(self) -> None:
        # "چھے" is a documented alias for 6 in urdu_numerals.json
        tokens = ["چھے"]
        assert parse_number_words(tokens) == 6


# ---------------------------------------------------------------------------
# §8 — Digit folding (Urdu-Indic and Arabic-Indic digits -> ASCII)
# ---------------------------------------------------------------------------

class TestDigitFolding:
    """
    docs/01 §2: Urdu-Indic (U+06F0-06F9) and Arabic-Indic (U+0660-0669)
    digits must fold to ASCII. Expected values from docs/01 §8.
    """

    def test_urdu_indic_digits_fold(self) -> None:
        # "۳۰۰" (U+06F3 U+06F0 U+06F0) -> "300"
        assert urdu_fold("۳۰۰") == "300"

    def test_arabic_indic_digits_fold(self) -> None:
        # U+0663 U+0660 U+0660 -> "300"
        assert urdu_fold("\u0663\u0660\u0660") == "300"

    def test_mixed_urdu_and_ascii_digits(self) -> None:
        # "۲ and 2" -> "2 and 2" (both forms become ASCII 2)
        # docs/01 §8: "Mixed ۲ and 2 in one utterance → both → 2"
        result = urdu_fold("۲ اور 2")
        assert "2" in result
        # both digit tokens resolve to the same ASCII character
        digits = [c for c in result if c.isdigit()]
        assert all(d == "2" for d in digits)

    def test_alef_variants_fold(self) -> None:
        # U+0623 -> U+0627, U+0622 -> U+0627, U+0625 -> U+0627
        assert urdu_fold("\u0623") == urdu_fold("\u0627")
        assert urdu_fold("\u0622") == urdu_fold("\u0627")
        assert urdu_fold("\u0625") == urdu_fold("\u0627")

    def test_yeh_variants_fold(self) -> None:
        # U+064A -> U+06CC, U+0649 -> U+06CC
        assert urdu_fold("\u064A") == urdu_fold("\u06CC")
        assert urdu_fold("\u0649") == urdu_fold("\u06CC")

    def test_heh_variants_fold(self) -> None:
        # U+0629, U+0647, U+06BE -> U+06C1
        assert urdu_fold("\u0629") == urdu_fold("\u06C1")
        assert urdu_fold("\u0647") == urdu_fold("\u06C1")
        assert urdu_fold("\u06BE") == urdu_fold("\u06C1")

    def test_kaf_variant_folds(self) -> None:
        # U+0643 -> U+06A9
        assert urdu_fold("\u0643") == urdu_fold("\u06A9")

    def test_diacritics_stripped(self) -> None:
        # Diacritics in range U+064B-U+065F and U+0670 must be removed
        word_with_diacritic = "\u0633\u064E\u0627\u062A"  # سَات with fatha
        assert urdu_fold(word_with_diacritic) == urdu_fold("سات")

    def test_zero_width_stripped(self) -> None:
        # Zero-width chars U+200B-U+200F stripped
        assert urdu_fold("\u200Bسات\u200C") == "سات"

    def test_whitespace_collapsed(self) -> None:
        assert urdu_fold("  سات   ") == "سات"
