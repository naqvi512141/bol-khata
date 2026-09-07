"""Normalizer module for Bol Khata.

Pipeline stage (d): normalizer.
Handles digit and orthographic folding, cardinal and compound number parsing,
fractional quantifier resolution, units canonicalization, and typed tokenization.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from app.normalizer.folding import urdu_fold
from app.normalizer.numbers import CARDINALS, MULTIPLIERS, parse_number_words
from app.normalizer.quantifiers import (
    MODIFIER,
    STANDALONE,
    resolve_quantifier,
)
from app.normalizer.tokenize import (
    Token,
    TokenType,
    classify_do,
    tokenize,
)
from app.normalizer.units import (
    UNITS_CANON,
    disambiguate_paw,
    resolve_unit,
)


@dataclass(frozen=True)
class TokenStream:
    """Stream of normalized and typed tokens for an utterance."""

    raw_text: str
    normalized_text: str
    tokens: list[Token]

    def __iter__(self) -> Iterator[Token]:
        return iter(self.tokens)

    def __len__(self) -> int:
        return len(self.tokens)

    def __getitem__(self, idx: int) -> Token:
        return self.tokens[idx]


def normalize(text: str) -> TokenStream:
    """Normalize raw Urdu transcript text into a typed TokenStream."""
    tokens = tokenize(text)
    normalized_text = urdu_fold(text)
    return TokenStream(
        raw_text=text,
        normalized_text=normalized_text,
        tokens=tokens,
    )


__all__ = [
    "CARDINALS",
    "MODIFIER",
    "MULTIPLIERS",
    "STANDALONE",
    "UNITS_CANON",
    "Token",
    "TokenStream",
    "TokenType",
    "classify_do",
    "disambiguate_paw",
    "normalize",
    "parse_number_words",
    "resolve_quantifier",
    "resolve_unit",
    "tokenize",
    "urdu_fold",
]
