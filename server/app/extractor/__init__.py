"""Extractor module for Bol Khata.

Pipeline stage (e): extractor.
Order-independent slot filling per docs/02-contracts.md §3 and docs/01-domain-urdu.md §8.
"""

from __future__ import annotations

from app.extractor.grouping import group_line_items
from app.extractor.matching import match_customer, match_sku
from app.extractor.ngram import Span, scan_customer_ngrams, scan_sku_ngrams
from app.extractor.residue import attribute_residue, collect_residue
from app.normalizer.folding import urdu_fold
from app.normalizer.tokenize import TokenType, classify_token
from app.schemas import (
    SKU,
    Customer,
    Issue,
    OrderForm,
    ParsedDraft,
    ValidationResult,
)

ORDER_PENALTY: dict[OrderForm, float] = {
    "canonical": 1.00,
    "name_last": 0.92,
    "name_medial": 0.88,
    "no_name_draft": 0.95,
    "no_name_cash": 0.85,
}


def _normalize_token_input(tokens: list[str] | str) -> tuple[list[str], list[str]]:
    """Convert input string or list of tokens into (raw_words, folded_words)."""
    if isinstance(tokens, str):
        cleaned_raw = tokens.replace("،", " ").replace(",", " ")
        raw_words = [w for w in cleaned_raw.split() if w]
        folded_words = [urdu_fold(w) for w in raw_words]
        return raw_words, folded_words
    raw_words = [w.strip() for w in tokens if w.strip()]
    folded_words = [urdu_fold(w) for w in raw_words]
    return raw_words, folded_words


def extract(
    tokens: list[str] | str,
    catalogue: list[SKU],
    customers: list[Customer],
    open_draft: str | None = None,
    shop_id: str = "demo_shop_01",
    draft_id: str = "d_extract_01",
    job_ids: list[str] | None = None,
) -> ParsedDraft:
    """Extract a structured ParsedDraft from tokens using the six-pass algorithm.

    Per docs/02-contracts.md §3:
      PASS 1: Label closed classes (numbers, quantifiers, units, fillers, etc.)
      PASS 2: n-gram SKU match (longest span first, 4..1)
      PASS 3: n-gram customer match (longest span first, 3..1)
      PASS 4: Group line items (adjacent QTY/UNIT/ITEM/MONEY)
      PASS 5: Collect residue
      PASS 6: Attribute customer, determine order_form and payment_type
    """
    raw_words, words = _normalize_token_input(tokens)
    num_words = len(words)
    labels: list[str | None] = [None] * num_words

    # -------------------------------------------------------------------------
    # PASS 1: Label closed classes
    # -------------------------------------------------------------------------
    for i in range(num_words):
        w = words[i]
        t_type = classify_token(w, words, i)
        if t_type == TokenType.QUANTITY:
            # Check if this quantity is followed by currency -> MONEY
            if i + 1 < num_words and classify_token(words[i + 1], words, i + 1) == TokenType.CURRENCY:
                labels[i] = "MONEY"
            else:
                labels[i] = "QTY"
        elif t_type == TokenType.UNIT:
            labels[i] = "UNIT"
        elif t_type == TokenType.CURRENCY:
            labels[i] = "CURRENCY"
        elif t_type == TokenType.HONORIFIC:
            labels[i] = "HONORIFIC"
        elif t_type == TokenType.GENITIVE:
            labels[i] = "GENITIVE"
        elif t_type == TokenType.FILLER:
            labels[i] = "FILLER"
        elif t_type == TokenType.NEGATION:
            labels[i] = "NEGATION"
        elif t_type == TokenType.UDHAAR:
            labels[i] = "UDHAAR"
        elif t_type == TokenType.CASH:
            labels[i] = "CASH"
        elif t_type == TokenType.QUERY:
            labels[i] = "QUERY"
        else:
            labels[i] = None

    # -------------------------------------------------------------------------
    # PASS 2: n-gram SKU match (longest span first)
    # -------------------------------------------------------------------------
    sku_spans = scan_sku_ngrams(words, labels, catalogue)

    # -------------------------------------------------------------------------
    # PASS 3: n-gram customer match (longest span first)
    # Consumes both resolved and ambiguous matches.
    # -------------------------------------------------------------------------
    cust_spans = scan_customer_ngrams(words, labels, customers)

    # -------------------------------------------------------------------------
    # PASS 4: Group line items
    # -------------------------------------------------------------------------
    line_items, consumed, grouping_issues = group_line_items(
        words, labels, sku_spans, catalogue, raw_tokens=raw_words
    )

    # -------------------------------------------------------------------------
    # PASS 5: Collect residue
    # -------------------------------------------------------------------------
    all_spans: list[Span] = list(sku_spans) + list(cust_spans)
    residue = collect_residue(words, labels, all_spans, consumed)

    # -------------------------------------------------------------------------
    # PASS 6: Attribute residue into customer, order_form, payment_type
    # -------------------------------------------------------------------------
    customer, order_form, payment_type, attribution_issues = attribute_residue(
        residue=residue,
        customer_spans=cust_spans,
        line_items=line_items,
        labels=labels,
        customers=customers,
        open_draft=open_draft,
    )

    # Combine validation issues
    blocking_issues: list[Issue] = list(grouping_issues) + list(attribution_issues)
    is_passed = len(blocking_issues) == 0

    validation = ValidationResult(
        passed=is_passed,
        blocking=blocking_issues,
        warnings=[],
        requires_llm=not is_passed and any(iss.rule not in ("V6", "V7") for iss in blocking_issues),
    )

    # Confidence calculation per docs/02-contracts.md §5
    sku_conf = min([it.match_score for it in line_items] or [0.0])
    cust_conf = customer.confidence if customer.status == "resolved" else 0.0
    val_score = 1.0 if validation.passed else 0.0
    base_conf = (
        0.35 * 1.0  # text input confidence
        + 0.20 * sku_conf
        + 0.20 * cust_conf
        + 0.10 * 0.80
        + 0.15 * val_score
    )
    conf = round(base_conf * ORDER_PENALTY.get(order_form, 1.0), 3)

    # Computed total in integer PKR (AGENTS.md rule 1)
    computed_total = sum(
        it.line_total if it.line_total is not None else 0 for it in line_items
    )

    return ParsedDraft(
        draft_id=draft_id,
        job_ids=job_ids or ["j_default"],
        shop_id=shop_id,
        customer=customer,
        items=line_items,
        residue=residue,
        stated_total=None,
        computed_total=int(computed_total),
        payment_type=payment_type,  # type: ignore[arg-type]
        currency="PKR",
        order_form=order_form,
        confidence=conf,
        path="fast" if is_passed else "manual",
        validation=validation,
        normalized_tokens=" ".join(words),
        raw_texts=[tokens if isinstance(tokens, str) else " ".join(tokens)],
    )


__all__ = [
    "ORDER_PENALTY",
    "Span",
    "attribute_residue",
    "collect_residue",
    "extract",
    "group_line_items",
    "match_customer",
    "match_sku",
    "scan_customer_ngrams",
    "scan_sku_ngrams",
]
