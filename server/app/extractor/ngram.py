"""Longest-span-first n-gram scanner for SKUs and Customers.

Per docs/02-contracts.md §3 (Pass 2 & Pass 3), AGENTS.md rule 7.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.extractor.matching import match_customer, match_sku
from app.schemas import SKU, Customer


@dataclass
class Span:
    """A matched token span for an item or customer."""

    start: int
    end: int
    label: str  # "ITEM" | "CUST"
    ref_id: str | None
    score: float
    match_status: str = "resolved"  # "resolved" | "ambiguous"
    raw_name: str = ""
    display_name: str | None = None
    candidates: list[str] = field(default_factory=list)


def scan_sku_ngrams(
    tokens: list[str],
    labels: list[str | None],
    catalogue: list[SKU],
) -> list[Span]:
    """Pass 2: n-gram SKU match, longest span first (4, 3, 2, 1).

    Skip any span already labelled. Longest match claims its tokens.
    """
    spans: list[Span] = []
    num_tokens = len(tokens)

    # Longest span first: 4 tokens down to 1
    max_span = min(4, num_tokens)
    for n in range(max_span, 0, -1):
        for i in range(num_tokens - n + 1):
            # If any token in this span is already claimed, skip
            if any(labels[i : i + n]):
                continue

            span_text = " ".join(tokens[i : i + n])
            m = match_sku(span_text, catalogue)
            if m.status == "resolved":
                for j in range(i, i + n):
                    labels[j] = "ITEM"
                spans.append(
                    Span(
                        start=i,
                        end=i + n,
                        label="ITEM",
                        ref_id=m.target_id,
                        score=m.score,
                        match_status="resolved",
                        raw_name=span_text,
                        display_name=m.display_name,
                        candidates=m.candidates,
                    )
                )

    return spans


def scan_customer_ngrams(
    tokens: list[str],
    labels: list[str | None],
    customers: list[Customer],
) -> list[Span]:
    """Pass 3: n-gram customer match, longest span first (3, 2, 1).

    Consumes BOTH resolved and ambiguous matches to prevent re-reading as product.
    Span carries match_status for Pass 6.
    """
    spans: list[Span] = []
    num_tokens = len(tokens)

    max_span = min(3, num_tokens)
    for n in range(max_span, 0, -1):
        for i in range(num_tokens - n + 1):
            if any(labels[i : i + n]):
                continue

            span_text = " ".join(tokens[i : i + n])
            m = match_customer(span_text, customers)
            if m.status in ("resolved", "ambiguous"):
                for j in range(i, i + n):
                    labels[j] = "CUST"
                spans.append(
                    Span(
                        start=i,
                        end=i + n,
                        label="CUST",
                        ref_id=m.target_id,
                        score=m.score,
                        match_status=m.status,
                        raw_name=span_text,
                        display_name=m.display_name,
                        candidates=m.candidates,
                    )
                )

    return spans
