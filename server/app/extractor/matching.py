"""Matching algorithms for SKUs and Customers.

Per docs/02-contracts.md §4, AGENTS.md rules 7, 8, 9.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from rapidfuzz import fuzz

from app.normalizer.folding import urdu_fold
from app.schemas import SKU, Customer

# Matching thresholds from docs/02-contracts.md §4
SKU_ACCEPT_SCORE: float = 88.0
SKU_MARGIN: float = 8.0
SKU_AMBIGUOUS_MIN: float = 70.0
SKU_FREQ_PRIOR: float = 0.05

CUST_ACCEPT_SCORE: float = 75.0
CUST_MARGIN: float = 10.0
CUST_RECENCY_HALF_LIFE_DAYS: float = 21.0
CUST_OPEN_BALANCE_BOOST: float = 1.15


@dataclass
class MatchResult:
    """Result of an SKU or Customer match."""

    status: Literal["resolved", "ambiguous", "unknown", "provisional"]
    target_id: str | None
    score: float
    margin: float
    candidates: list[str] = field(default_factory=list)
    raw_name: str = ""
    display_name: str | None = None

    def __post_init__(self) -> None:
        self.score = max(0.0, min(100.0, float(self.score)))

    @property
    def sku_id(self) -> str | None:
        """Alias target_id for SKU matches."""
        return self.target_id

    @property
    def customer_id(self) -> str | None:
        """Alias target_id for Customer matches."""
        return self.target_id


def _score_similarity(query: str, candidate: str) -> float:
    """Score query against candidate name.

    If token counts match, use WRatio for fuzzy token/case handling.
    If token counts differ, use full ratio to prevent 1-token names from
    greedily absorbing adjacent words during multi-token n-gram scans.
    """
    q_tokens = query.split()
    c_tokens = candidate.split()
    if len(q_tokens) == len(c_tokens):
        return float(fuzz.WRatio(query, candidate))
    return float(fuzz.ratio(query, candidate))


def match_sku(query: str, catalogue: list[SKU]) -> MatchResult:
    """Match a token span against the catalogue with threshold + margin check.

    Per docs/02-contracts.md §4 & AGENTS.md rule 8:
      - Ranking uses boosted scores (priors break ties).
      - Acceptance strictly requires RAW pre-prior score >= SKU_ACCEPT_SCORE (88).
      - Top raw score >= 88 and margin >= 8 points clear of runner-up -> resolved
      - Top raw score >= 70 but margin < 8 -> ambiguous
      - Top raw score < 70 -> unknown
      - Margin check compares candidates on the same score basis (boosted vs boosted).
      - Reported score is clamped to [0.0, 100.0].
    """
    folded_query = urdu_fold(query).strip()
    if not folded_query:
        return MatchResult(
            status="unknown", target_id=None, score=0.0, margin=0.0, raw_name=query
        )

    scored: list[tuple[float, float, SKU]] = []
    for sku in catalogue:
        names_to_check = [sku.display_name] + sku.aliases
        best_sim = max(
            _score_similarity(folded_query, urdu_fold(name).strip())
            for name in names_to_check
        )
        raw_score = float(best_sim)
        boosted_score = raw_score
        sale_count = len(sku.price_history)
        if sale_count > 0:
            boosted_score *= 1.0 + SKU_FREQ_PRIOR * math.log1p(sale_count)
        scored.append((boosted_score, raw_score, sku))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    if not scored:
        return MatchResult(
            status="unknown", target_id=None, score=0.0, margin=0.0, raw_name=query
        )

    s1_boosted, s1_raw, top_sku = scored[0]
    s2_boosted, s2_raw = (scored[1][0], scored[1][1]) if len(scored) > 1 else (0.0, 0.0)
    raw_margin = s1_raw - s2_raw
    boosted_margin = s1_boosted - s2_boosted
    margin = min(raw_margin, boosted_margin)

    reported_score = max(0.0, min(100.0, s1_boosted))

    # Accept decision requires RAW pre-prior score to meet threshold and BOTH margins to pass
    if s1_raw >= SKU_ACCEPT_SCORE and raw_margin >= SKU_MARGIN and boosted_margin >= SKU_MARGIN:
        return MatchResult(
            status="resolved",
            target_id=top_sku.sku_id,
            score=reported_score,
            margin=margin,
            candidates=[top_sku.sku_id],
            raw_name=query,
            display_name=top_sku.display_name,
        )
    elif s1_raw >= SKU_AMBIGUOUS_MIN:
        ambiguous_candidates = [
            sku.sku_id for _, raw, sku in scored if raw >= SKU_AMBIGUOUS_MIN
        ]
        return MatchResult(
            status="ambiguous",
            target_id=None,
            score=reported_score,
            margin=margin,
            candidates=ambiguous_candidates,
            raw_name=query,
            display_name=top_sku.display_name,
        )
    else:
        return MatchResult(
            status="unknown",
            target_id=None,
            score=reported_score,
            margin=margin,
            raw_name=query,
        )


def _compute_customer_boost(cust: Customer) -> float:
    """Compute prior multiplier for a customer based on balance and recency."""
    boost = 1.0
    if cust.balance > 0:
        boost *= CUST_OPEN_BALANCE_BOOST

    if cust.last_txn_at:
        try:
            txn_dt = datetime.fromisoformat(cust.last_txn_at)
            ref_time = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
            diff_seconds = (ref_time - txn_dt.astimezone(UTC)).total_seconds()
            days = max(0.0, diff_seconds / 86400.0)
            recency_weight = 0.5 ** (days / CUST_RECENCY_HALF_LIFE_DAYS)
            boost *= 1.0 + 0.10 * recency_weight
        except (ValueError, TypeError):
            pass
    return boost


def match_customer(query: str, customers: list[Customer]) -> MatchResult:
    """Match a token span against the customer list with threshold, margin, and priors.

    Per docs/02-contracts.md §4 & AGENTS.md rule 8:
      - Ranking uses boosted scores (priors break ties).
      - Acceptance strictly requires RAW pre-prior score >= CUST_ACCEPT_SCORE (75).
      - Requires BOTH raw_margin >= 10 and boosted_margin >= 10 to resolve.
      - Top raw score >= 75 and both margins >= 10 -> resolved
      - Top raw score >= 75 but either margin < 10 -> ambiguous
      - Top raw score < 75 -> unknown (matches nothing, per docs/02 §3 residue table)
      - Reported score is clamped to [0.0, 100.0].
    """
    folded_query = urdu_fold(query).strip()
    if not folded_query:
        return MatchResult(
            status="unknown", target_id=None, score=0.0, margin=0.0, raw_name=query
        )

    scored: list[tuple[float, float, Customer]] = []
    for cust in customers:
        names_to_check = [cust.display_name] + cust.aliases
        best_sim = max(
            _score_similarity(folded_query, urdu_fold(name).strip())
            for name in names_to_check
        )
        raw_score = float(best_sim)
        boost = _compute_customer_boost(cust)
        boosted_score = raw_score * boost
        scored.append((boosted_score, raw_score, cust))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    if not scored:
        return MatchResult(
            status="unknown", target_id=None, score=0.0, margin=0.0, raw_name=query
        )

    s1_boosted, s1_raw, top_cust = scored[0]
    s2_boosted, s2_raw = (scored[1][0], scored[1][1]) if len(scored) > 1 else (0.0, 0.0)
    raw_margin = s1_raw - s2_raw
    boosted_margin = s1_boosted - s2_boosted
    margin = min(raw_margin, boosted_margin)

    reported_score = max(0.0, min(100.0, s1_boosted))

    # Acceptance requires RAW pre-prior score to meet CUST_ACCEPT_SCORE (75.0)
    # AND both raw_margin >= CUST_MARGIN and boosted_margin >= CUST_MARGIN
    if s1_raw >= CUST_ACCEPT_SCORE and raw_margin >= CUST_MARGIN and boosted_margin >= CUST_MARGIN:
        return MatchResult(
            status="resolved",
            target_id=top_cust.customer_id,
            score=reported_score,
            margin=margin,
            candidates=[top_cust.customer_id],
            raw_name=query,
            display_name=top_cust.display_name,
        )
    elif s1_raw >= CUST_ACCEPT_SCORE:
        ambiguous_candidates = [
            c.customer_id for _, raw, c in scored if raw >= CUST_ACCEPT_SCORE
        ]
        return MatchResult(
            status="ambiguous",
            target_id=None,
            score=reported_score,
            margin=margin,
            candidates=ambiguous_candidates,
            raw_name=query,
            display_name=top_cust.display_name,
        )
    else:
        return MatchResult(
            status="unknown",
            target_id=None,
            score=reported_score,
            margin=margin,
            raw_name=query,
        )
