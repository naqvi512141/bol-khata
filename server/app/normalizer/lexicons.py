"""Lexicons for Urdu function words and markers.

Per docs/01-domain-urdu.md §6.
All lists are data, never conditions inside if branches (AGENTS.md rule 8).
"""

from __future__ import annotations

from app.normalizer.folding import urdu_fold

HONORIFICS: list[str] = [
    "بھائی",
    "صاحب",
    "جی",
    "باجی",
    "خالہ",
    "چاچا",
    "انکل",
    "آپا",
]

GENITIVE_MARKERS: list[str] = ["کا", "کی", "کے"]

FILLERS: list[str] = [
    "اچھا",
    "ٹھیک",
    "ہاں",
    "وہ",
    "یار",
    "دیکھو",
    "اور",
    "بس",
    "پھر",
]

NEGATION: list[str] = ["نہیں", "غلط", "رکو", "ایک منٹ"]

UDHAAR_MARKERS: list[str] = ["ادھار", "خاتہ", "لکھ لو", "لکھ دو", "khata", "udhaar"]

CASH_MARKERS: list[str] = ["نقد", "کیش", "ادا", "cash"]

CURRENCY: list[str] = ["روپے", "روپیہ", "rupay", "rupees", "PKR", "Rs"]

QUERY_MARKERS: list[str] = [
    "بیلنس",
    "حساب",
    "کتنا باقی",
    "کتنے پیسے",
    "کتنا ادھار",
    "آج کا",
    "balance",
]

# Folded lookup sets for normalized matching
HONORIFICS_FOLDED: frozenset[str] = frozenset(urdu_fold(w) for w in HONORIFICS)
GENITIVE_MARKERS_FOLDED: frozenset[str] = frozenset(urdu_fold(w) for w in GENITIVE_MARKERS)
FILLERS_FOLDED: frozenset[str] = frozenset(urdu_fold(w) for w in FILLERS)
NEGATION_FOLDED: frozenset[str] = frozenset(urdu_fold(w) for w in NEGATION)
UDHAAR_MARKERS_FOLDED: frozenset[str] = frozenset(urdu_fold(w) for w in UDHAAR_MARKERS)
CASH_MARKERS_FOLDED: frozenset[str] = frozenset(urdu_fold(w) for w in CASH_MARKERS)
CURRENCY_FOLDED: frozenset[str] = frozenset(urdu_fold(w) for w in CURRENCY)
QUERY_MARKERS_FOLDED: frozenset[str] = frozenset(urdu_fold(w) for w in QUERY_MARKERS)
