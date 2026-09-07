"""
tests/normalizer/test_tokenize.py
Tests for app/normalizer/tokenize.py and the do-homophone classifier.

Expected values are authoritative — from docs/01-domain-urdu.md §7 and §8.
Do not change expected values to make the implementation pass.
"""
from __future__ import annotations

import pytest

from app.normalizer.tokenize import TokenType, classify_do, tokenize


# ---------------------------------------------------------------------------
# §7 — دو (do) homophone disambiguation
# "do" (دو) is the highest-frequency ambiguity. docs/01 §7.
# ---------------------------------------------------------------------------

class TestClassifyDo:
    """
    docs/01 §7: classify_do returns "NUMERAL", "VERB", or "AMBIGUOUS".
    All three outcomes must be reachable.
    """

    def test_do_before_unit_is_numeral(self) -> None:
        # "do kilo" -> NUMERAL (docs/01 §7 + §8)
        tokens = ["دو", "کلو"]
        assert classify_do(tokens, 0) == "NUMERAL"

    def test_de_do_is_verb(self) -> None:
        # "de do" -> VERB (prev is in IMPERATIVE_HEADS) (docs/01 §7 + §8)
        tokens = ["دے", "دو"]
        assert classify_do(tokens, 1) == "VERB"

    def test_do_before_known_item_is_numeral(self) -> None:
        # If next token is a known item name -> NUMERAL (docs/01 §7)
        # Use a token that is in the SKU alias set
        tokens = ["دو", "چینی"]
        assert classify_do(tokens, 0) == "NUMERAL"

    def test_do_at_end_is_verb(self) -> None:
        # "de do" pattern: do at the very end with no next token -> VERB
        tokens = ["دے", "دو"]
        assert classify_do(tokens, 1) == "VERB"

    def test_do_before_digit_is_numeral(self) -> None:
        # next token is a digit string -> NUMERAL (docs/01 §7)
        tokens = ["دو", "3"]
        assert classify_do(tokens, 0) == "NUMERAL"


# ---------------------------------------------------------------------------
# §8 — tokenize integration test (folding → splitting → typed stream)
# ---------------------------------------------------------------------------

class TestTokenize:
    """
    tokenize() must: fold input, split on whitespace, emit a typed token stream.
    The stream must include the folded text for each token.
    """

    def test_tokenize_returns_list(self) -> None:
        result = tokenize("دو کلو چینی")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_each_token_has_type_and_text(self) -> None:
        result = tokenize("دو کلو")
        for tok in result:
            assert hasattr(tok, "text")
            assert hasattr(tok, "token_type")
            assert isinstance(tok.token_type, TokenType)

    def test_urdu_indic_digit_folded_in_stream(self) -> None:
        # "۳۰۰" in the input should produce a token with folded text "300"
        result = tokenize("۳۰۰")
        assert any(tok.text == "300" for tok in result), (
            f"Expected '300' in token stream, got: {[tok.text for tok in result]}"
        )

    def test_filler_token_typed(self) -> None:
        # "اچھا" is a filler (docs/01 §6) — should be typed FILLER
        result = tokenize("اچھا دو کلو")
        types = [tok.token_type for tok in result]
        assert TokenType.FILLER in types

    def test_unit_token_typed(self) -> None:
        result = tokenize("دو کلو")
        types = [tok.token_type for tok in result]
        assert TokenType.UNIT in types

    def test_quantity_token_typed(self) -> None:
        result = tokenize("دو کلو")
        types = [tok.token_type for tok in result]
        assert TokenType.QUANTITY in types

    def test_honorific_token_typed(self) -> None:
        # "بھائی" is an honorific (docs/01 §6)
        result = tokenize("احمد بھائی")
        types = [tok.token_type for tok in result]
        assert TokenType.HONORIFIC in types

    def test_genitive_token_typed(self) -> None:
        # "کا" is a genitive marker (docs/01 §6)
        result = tokenize("احمد کا")
        types = [tok.token_type for tok in result]
        assert TokenType.GENITIVE in types

    def test_whitespace_collapsed_before_split(self) -> None:
        result_single = tokenize("دو کلو")
        result_multi = tokenize("دو   کلو")
        assert [t.text for t in result_single] == [t.text for t in result_multi]
