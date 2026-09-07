"""Tokenization and homophone classification for Urdu text.

Per docs/01-domain-urdu.md §2, §6, §7.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.normalizer.folding import urdu_fold
from app.normalizer.lexicons import (
    CASH_MARKERS_FOLDED,
    CURRENCY_FOLDED,
    FILLERS_FOLDED,
    GENITIVE_MARKERS_FOLDED,
    HONORIFICS_FOLDED,
    NEGATION_FOLDED,
    QUERY_MARKERS_FOLDED,
    UDHAAR_MARKERS_FOLDED,
)
from app.normalizer.numbers import CARDINALS, MULTIPLIERS
from app.normalizer.quantifiers import MODIFIER, STANDALONE
from app.normalizer.units import UNITS_CANON

# Homophone imperative heads from docs/01-domain-urdu.md §7
IMPERATIVE_HEADS: frozenset[str] = frozenset(
    urdu_fold(w) for w in ["دے", "لے", "کر"]
)

_DO_FOLDED = urdu_fold("دو")

_CATALOGUE_PATH = Path(__file__).resolve().parents[2] / "data" / "catalogue.json"


def _load_catalogue_item_tokens() -> frozenset[str]:
    if not _CATALOGUE_PATH.exists():
        return frozenset()
    with open(_CATALOGUE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    tokens: set[str] = set()
    for item in data:
        name = item.get("display_name", "")
        for tok in urdu_fold(name).split():
            tokens.add(tok)
        for alias in item.get("aliases", []):
            for tok in urdu_fold(alias).split():
                tokens.add(tok)
    return frozenset(tokens)


KNOWN_ITEM_TOKENS: frozenset[str] = _load_catalogue_item_tokens()


class TokenType(str, Enum):
    FILLER = "FILLER"
    HONORIFIC = "HONORIFIC"
    GENITIVE = "GENITIVE"
    NEGATION = "NEGATION"
    UDHAAR = "UDHAAR"
    CASH = "CASH"
    CURRENCY = "CURRENCY"
    QUERY = "QUERY"
    UNIT = "UNIT"
    QUANTITY = "QUANTITY"
    WORD = "WORD"


@dataclass(frozen=True)
class Token:
    text: str
    token_type: TokenType
    index: int


def classify_do(tokens: list[str], i: int) -> str:
    """Classify the ambiguous token 'دو' (two vs give) per docs/01-domain-urdu.md §7.

    Returns:
      'NUMERAL'    if preceding/succeeding tokens indicate a quantity.
      'VERB'       if following an imperative head or at end of line.
      'AMBIGUOUS'  otherwise (must block for confirmation).
    """
    nxt = urdu_fold(tokens[i + 1]) if i + 1 < len(tokens) else None
    prev = urdu_fold(tokens[i - 1]) if i > 0 else None

    if nxt is not None and (
        nxt in UNITS_CANON or nxt in KNOWN_ITEM_TOKENS or nxt.isdigit()
    ):
        return "NUMERAL"

    if prev in IMPERATIVE_HEADS or nxt is None:
        return "VERB"

    return "AMBIGUOUS"


def classify_token(word: str, tokens: list[str], i: int) -> TokenType:
    """Classify a single folded word into its TokenType."""
    if word in FILLERS_FOLDED:
        return TokenType.FILLER
    if word in HONORIFICS_FOLDED:
        return TokenType.HONORIFIC
    if word in GENITIVE_MARKERS_FOLDED:
        return TokenType.GENITIVE
    if word in NEGATION_FOLDED:
        return TokenType.NEGATION
    if word in UDHAAR_MARKERS_FOLDED:
        return TokenType.UDHAAR
    if word in CASH_MARKERS_FOLDED:
        return TokenType.CASH
    if word in CURRENCY_FOLDED:
        return TokenType.CURRENCY
    if word in QUERY_MARKERS_FOLDED:
        return TokenType.QUERY
    if word in UNITS_CANON:
        return TokenType.UNIT

    if word == _DO_FOLDED:
        classification = classify_do(tokens, i)
        if classification == "NUMERAL":
            return TokenType.QUANTITY
        if classification == "VERB":
            return TokenType.FILLER
        return TokenType.WORD

    if (
        word in CARDINALS
        or word in MULTIPLIERS
        or word in STANDALONE
        or word in MODIFIER
        or word.isdigit()
    ):
        return TokenType.QUANTITY

    return TokenType.WORD


def tokenize(text: str) -> list[Token]:
    """Fold, split on whitespace, and emit a typed token stream."""
    folded = urdu_fold(text)
    words = folded.split()

    result: list[Token] = []
    for i, w in enumerate(words):
        t_type = classify_token(w, words, i)
        result.append(Token(text=w, token_type=t_type, index=i))

    return result
