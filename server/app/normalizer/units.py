"""Unit canonical definitions and paw disambiguation.

Per docs/01-domain-urdu.md §5.
"""

from __future__ import annotations

from typing import Any

from app.normalizer.folding import urdu_fold

# Units canonically defined in docs/01-domain-urdu.md §5
# word -> ((unit_code, factor), original_urdu)
_UNITS_SPEC: list[tuple[str, tuple[str, float]]] = [
    ("کلو", ("kg", 1.0)),  # kilo
    ("کلوگرام", ("kg", 1.0)),  # kilogram
    ("گرام", ("g", 1.0)),  # gram
    ("پاؤ", ("kg", 0.25)),  # paw -- UNIT sense
    ("سیر", ("kg", 0.933)),  # seer
    ("چھٹانک", ("g", 58.3)),  # chhataank
    ("درجن", ("dozen", 12.0)),  # darjan
    ("لیٹر", ("l", 1.0)),  # litre
    ("بوتل", ("bottle", 1.0)),  # bottle
    ("پیکٹ", ("packet", 1.0)),  # packet
    ("ڈبہ", ("box", 1.0)),  # dabba
]

# Folded dictionary lookup
UNITS_CANON: dict[str, tuple[str, float]] = {
    urdu_fold(word): spec for word, spec in _UNITS_SPEC
}


def resolve_unit(word: str) -> tuple[str, float] | None:
    """Resolve an Urdu word to its canonical (unit_code, factor) or None."""
    return UNITS_CANON.get(urdu_fold(word))


def disambiguate_paw(
    next_token: str | None = None,
    sku_default_unit: str | None = None,
) -> dict[str, Any]:
    """Disambiguate the dual meaning of 'paw' per docs/01-domain-urdu.md §5.

    paw always yields 0.25 of the item's mass unit.
    1. Next token is a unit -> paw is a quantifier: 0.25 x that unit (e.g. 'paw kilo' = 0.25 kg).
    2. Next token is an item -> paw is the unit itself (250 g = 0.25 kg) (e.g. 'paw cheeni' = 0.25 kg).
    3. paw stands alone (no following token) -> default to 0.25 kg.
    4. If resolved SKU's default_unit is not a mass unit ('kg' or 'g') -> ambiguous -> blocking.
    """
    if sku_default_unit is not None and sku_default_unit not in ("kg", "g"):
        return {"role": "blocking", "qty": None, "unit": None}

    if next_token is not None:
        unit_info = resolve_unit(next_token)
        if unit_info is not None:
            return {"role": "quantifier", "qty": 0.25, "unit": unit_info[0]}

    unit = sku_default_unit if sku_default_unit in ("kg", "g") else "kg"
    return {"role": "unit", "qty": 0.25, "unit": unit}
