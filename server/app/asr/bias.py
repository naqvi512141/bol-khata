"""Bias prompt builder for Whisper ASR.

Per docs/03-build-plan.md Phase 5:
Fixed numeral lexicon + top ~35 SKUs by recency-weighted frequency + top ~10 active customer names,
capped at ~200 tokens.

Prompt helps Whisper bias toward Urdu commercial vocabulary and avoids misrecognizing
shop names, units, quantities, and customer names.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from app.schemas import SKU, Customer

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Core commercial words and units
COMMERCIAL_WORDS: list[str] = [
    "روپے", "روپیہ", "ادھار", "نقد", "کیش", "خاتہ", "کلو", "گرام", "درجن", "پیکٹ", "بوتل",
]

# Core cardinal numbers and quantifiers
CORE_NUMERALS: list[str] = [
    "ایک", "دو", "تین", "چار", "پانچ", "چھ", "سات", "آٹھ", "نو", "دس",
    "پندرہ", "بیس", "پچیس", "پچاس", "سو", "ہزار", "لاکھ",
]

QUANTIFIER_WORDS: list[str] = [
    "آدھا", "پاؤ", "ڈیڑھ", "ڈھائی", "سوا", "ساڑھے", "پونے",
]

ADDITIONAL_NUMERALS: list[str] = [
    "گیارہ", "بارہ", "تیرہ", "چودہ", "سولہ", "سترہ", "اٹھارہ", "انیس",
    "تیس", "پینتیس", "چالیس", "ساٹھ", "ستر", "اسی", "نوے",
]

URDU_RE = re.compile(r"[\u0600-\u06FF]")


def is_urdu(text: str) -> bool:
    """Return True if text contains Urdu/Arabic script."""
    return bool(URDU_RE.search(text))


def estimate_token_count(text: str) -> int:
    """Conservative estimation of Whisper byte-level BPE tokens for Urdu text.

    In Whisper's byte-level BPE:
    - Urdu script characters are 2 UTF-8 bytes each.
    - Common Urdu letters and letter pairs map to 1 token (~1.2 tokens per 2-3 characters).
    - Punctuation / delimiters take ~1 token each.
    This estimator ensures the prompt remains safely within the ~200 token budget.
    """
    if not text.strip():
        return 0

    tokens = 0
    words = text.split()
    for w in words:
        if is_urdu(w):
            # ~1 token per 2-3 characters, at least 1 token per word
            tokens += max(1, math.ceil(len(w) * 0.7))
        else:
            tokens += max(1, math.ceil(len(w) / 3.0))
        # Account for inter-word space / delimiter token
        tokens += 1

    return tokens


def score_sku(sku: SKU, now_utc: datetime | None = None) -> float:
    """Calculate recency-weighted frequency score for a SKU."""
    history_count = len(sku.price_history)
    base_score = math.log1p(history_count + 1.0)

    if sku.last_sold_at:
        try:
            sold_time = datetime.fromisoformat(sku.last_sold_at)
            if now_utc is None:
                now_utc = datetime.now(UTC)
            if sold_time.tzinfo is None:
                sold_time = sold_time.replace(tzinfo=UTC)
            days_ago = max(0.0, (now_utc - sold_time).total_seconds() / 86400.0)
            recency = math.pow(0.5, days_ago / 21.0)
            return base_score * (1.0 + recency)
        except (ValueError, TypeError):
            return base_score

    return base_score


def score_customer(customer: Customer, now_utc: datetime | None = None) -> float:
    """Score customer activity by recency and open balance boost."""
    base_score = 1.0
    if customer.balance != 0:
        base_score *= 1.15  # docs/02-contracts.md §4 open balance boost

    if customer.last_txn_at:
        try:
            txn_time = datetime.fromisoformat(customer.last_txn_at)
            if now_utc is None:
                now_utc = datetime.now(UTC)
            if txn_time.tzinfo is None:
                txn_time = txn_time.replace(tzinfo=UTC)
            days_ago = max(0.0, (now_utc - txn_time).total_seconds() / 86400.0)
            recency = math.pow(0.5, days_ago / 21.0)
            return base_score * (1.0 + recency)
        except (ValueError, TypeError):
            return base_score

    return base_score


def load_default_catalogue() -> list[SKU]:
    """Load default catalogue from server/data/catalogue.json."""
    cat_file = DATA_DIR / "catalogue.json"
    if not cat_file.exists():
        return []
    with open(cat_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [SKU.model_validate(item) for item in data]


def load_default_customers() -> list[Customer]:
    """Load default customers from server/data/customers.json."""
    cust_file = DATA_DIR / "customers.json"
    if not cust_file.exists():
        return []
    with open(cust_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Customer.model_validate(item) for item in data]


def build_bias_prompt(
    catalogue: Sequence[SKU] | None = None,
    customers: Sequence[Customer] | None = None,
    max_tokens: int = 200,
) -> str:
    """Build vocabulary bias prompt capped at ~200 tokens.

    Assembles in priority order:
    1. Core commercial keywords and units (روپے, ادھار, کلو, etc.)
    2. Core numerals and quantifiers (ایک, دو, آدھا, etc.)
    3. Top active customer names (up to ~10)
    4. Top SKUs by recency-weighted frequency (up to ~35)
    5. Additional numerals if budget remains

    Never exceeds max_tokens.
    """
    if catalogue is None:
        catalogue = load_default_catalogue()
    if customers is None:
        customers = load_default_customers()

    selected_terms: list[str] = []
    seen_terms: set[str] = set()

    def try_add(term: str) -> bool:
        term = term.strip()
        if not term or term in seen_terms:
            return True
        candidate_terms = selected_terms + [term]
        candidate_prompt = "، ".join(candidate_terms)
        if estimate_token_count(candidate_prompt) > max_tokens:
            return False
        selected_terms.append(term)
        seen_terms.add(term)
        return True

    # 1. Core commercial keywords and units
    for w in COMMERCIAL_WORDS:
        if not try_add(w):
            break

    # 2. Core numerals and quantifiers
    for w in CORE_NUMERALS + QUANTIFIER_WORDS:
        if not try_add(w):
            break

    # 3. Top active customers (up to 10)
    sorted_customers = sorted(customers, key=score_customer, reverse=True)[:10]
    for cust in sorted_customers:
        if is_urdu(cust.display_name) and not try_add(cust.display_name):
            break
        for alias in cust.aliases:
            if is_urdu(alias) and not try_add(alias):
                break

    # 4. Top SKUs by recency-weighted frequency (up to 35)
    sorted_skus = sorted(catalogue, key=score_sku, reverse=True)[:35]
    for sku in sorted_skus:
        if is_urdu(sku.display_name) and not try_add(sku.display_name):
            break
        for alias in sku.aliases:
            if is_urdu(alias) and not try_add(alias):
                break

    # 5. Additional numerals if budget allows
    for w in ADDITIONAL_NUMERALS:
        if not try_add(w):
            break

    return "، ".join(selected_terms)
