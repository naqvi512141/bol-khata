"""Orthographic folding for Urdu text.

Per docs/01-domain-urdu.md §2:
Recognition output is inconsistent about which Unicode variant it emits for the
same letter. Fold before any comparison.

Order of operations in urdu_fold(s):
1. Strip zero-width characters (U+200B-U+200F, U+202A-U+202E, U+2066-U+2069)
2. Strip diacritics (U+064B-U+065F, U+0670, U+06D6-U+06ED)
3. Translate Urdu-Indic and Arabic-Indic digits to ASCII
4. Apply character folds (alef, yeh, heh, kaf variants)
5. Collapse whitespace and strip
"""

from __future__ import annotations

import re

# Urdu-Indic (U+06F0-06F9) and Arabic-Indic (U+0660-0669) digits -> ASCII
DIGIT_MAP = str.maketrans(
    "\u06F0\u06F1\u06F2\u06F3\u06F4\u06F5\u06F6\u06F7\u06F8\u06F9"
    "\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669",
    "01234567890123456789",
)

CHAR_FOLD_MAP = str.maketrans(
    {
        "\u0623": "\u0627",  # alef with hamza above -> alef
        "\u0622": "\u0627",  # alef with madda      -> alef
        "\u0625": "\u0627",  # alef with hamza below -> alef
        "\u064A": "\u06CC",  # arabic yeh  -> farsi yeh
        "\u0649": "\u06CC",  # alef maksura -> farsi yeh
        "\u0629": "\u06C1",  # teh marbuta -> heh goal
        "\u0647": "\u06C1",  # arabic heh  -> heh goal
        "\u06BE": "\u06C1",  # heh doachashmee -> heh goal
        "\u0643": "\u06A9",  # arabic kaf -> keheh
    }
)

_ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200F\u202A-\u202E\u2066-\u2069]")
_DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")


def urdu_fold(s: str) -> str:
    """Fold Urdu text to canonical form.

    Order:
    strip zero-width -> strip diacritics -> translate digits -> apply CHAR_FOLD
    -> collapse whitespace -> strip.
    """
    # 1. strip zero-width characters
    s = _ZERO_WIDTH_RE.sub("", s)
    # 2. strip diacritics
    s = _DIACRITICS_RE.sub("", s)
    # 3. translate digits
    s = s.translate(DIGIT_MAP)
    # 4. apply character folding
    s = s.translate(CHAR_FOLD_MAP)
    # 5. collapse whitespace & strip
    return " ".join(s.split())
