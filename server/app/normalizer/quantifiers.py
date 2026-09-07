"""Fractional quantifier parsing and resolution.

Per docs/01-domain-urdu.md §4:
Class A: Standalone values (aadha 0.5, paw 0.25, derh 1.5, dhai 2.5)
Class B: Prefix modifiers (sawa +0.25, saarhe +0.5, paun -0.25)

CRITICAL (AGENTS.md rule 3):
paun (پونے) SUBTRACTS 0.25. paun chaar = 3.75, NOT 4.25.
Dangling modifier with no following number returns None (blocking).
"""

from __future__ import annotations

from app.normalizer.folding import urdu_fold
from app.normalizer.numbers import CARDINALS, MULTIPLIERS, parse_number_words
from app.normalizer.units import resolve_unit

STANDALONE: dict[str, float] = {
    urdu_fold("آدھا"): 0.5,  # aadha
    urdu_fold("پاؤ"): 0.25,  # paw
    urdu_fold("ڈیڑھ"): 1.5,  # derh
    urdu_fold("ڈھائی"): 2.5,  # dhai
}

MODIFIER: dict[str, float] = {
    urdu_fold("سوا"): 0.25,  # sawa: +0.25
    urdu_fold("ساڑھے"): 0.5,  # saarhe: +0.5
    urdu_fold("پونے"): -0.25,  # paun: SUBTRACTS 0.25 (AGENTS.md rule 3)
}

_PAW_FOLDED = urdu_fold("پاؤ")


def resolve_quantifier(tokens: list[str], i: int) -> tuple[float | None, str | None]:
    """Resolve a quantifier at index `i` in `tokens`.

    Returns (quantity_float, unit_hint_str_or_None).
    If the quantifier is a dangling modifier with no following number, returns (None, None).
    """
    if i < 0 or i >= len(tokens):
        return None, None

    word = urdu_fold(tokens[i])

    if word in STANDALONE:
        base_val = STANDALONE[word]
        unit_hint: str | None = None
        if i + 1 < len(tokens):
            u = resolve_unit(tokens[i + 1])
            if u is not None:
                unit_hint = u[0]
            elif word == _PAW_FOLDED:
                # paw standing before an item or alone defaults to 0.25 kg
                unit_hint = "kg"
        elif word == _PAW_FOLDED:
            # paw alone with no following token defaults to 0.25 kg per docs/01 §5
            unit_hint = "kg"

        return base_val, unit_hint

    if word in MODIFIER:
        delta = MODIFIER[word]
        if i + 1 >= len(tokens):
            # Dangling modifier (docs/01 §4: return None, do not default)
            return None, None

        # Collect subsequent numeral tokens
        num_tokens: list[str] = []
        k = i + 1
        while k < len(tokens) and (
            urdu_fold(tokens[k]) in CARDINALS or urdu_fold(tokens[k]) in MULTIPLIERS
        ):
            num_tokens.append(tokens[k])
            k += 1

        if num_tokens:
            n = parse_number_words(num_tokens)
            if n is None:
                return None, None
            base_val = float(n)
        elif k < len(tokens) and urdu_fold(tokens[k]).isdigit():
            base_val = float(int(urdu_fold(tokens[k])))
            k += 1
        else:
            return None, None

        final_qty = base_val + delta

        unit_hint = None
        if k < len(tokens):
            u = resolve_unit(tokens[k])
            if u is not None:
                unit_hint = u[0]

        return final_qty, unit_hint

    return None, None
