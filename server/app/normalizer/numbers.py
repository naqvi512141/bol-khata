"""Cardinal and compound numeral parsing for Urdu words.

Per docs/01-domain-urdu.md §3:
Cardinals 0-99 and multipliers (sau 100, hazaar 1000, lakh 100000).
Asymmetric algorithm: 100 multiplies current group in place; 1000+ flushes group.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.normalizer.folding import urdu_fold

_DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "urdu_numerals.json"


def _load_numeral_data() -> tuple[dict[str, int], dict[str, int]]:
    with open(_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    cardinals: dict[str, int] = {}
    for word, val in data.get("cardinals", {}).items():
        cardinals[urdu_fold(word)] = val
    for word, val in data.get("cardinal_aliases", {}).items():
        cardinals[urdu_fold(word)] = val

    multipliers: dict[str, int] = {}
    for word, val in data.get("multipliers", {}).items():
        multipliers[urdu_fold(word)] = val

    return cardinals, multipliers


CARDINALS, MULTIPLIERS = _load_numeral_data()


def parse_number_words(tokens: list[str]) -> int | None:
    """Parse a sequence of Urdu numeral words using the compound number algorithm.

    Algorithm from docs/01-domain-urdu.md §3:
    100 multiplies the current group in place.
    1000 and above flush the group into the running total.
    Stops at the first non-number token.
    """
    total: int = 0
    current: int = 0
    seen: bool = False

    for t in tokens:
        folded = urdu_fold(t)
        if folded in CARDINALS:
            current += CARDINALS[folded]
            seen = True
        elif folded in MULTIPLIERS:
            m = MULTIPLIERS[folded]
            if m == 100:
                current = (current or 1) * 100
            else:
                total += (current or 1) * m
                current = 0
            seen = True
        else:
            break

    return (total + current) if seen else None
