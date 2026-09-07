"""Residue collection and attribution rules.

Per docs/02-contracts.md §3 (Pass 5 & Pass 6) and docs/01-domain-urdu.md §8.
"""

from __future__ import annotations

from app.extractor.matching import match_customer
from app.extractor.ngram import Span
from app.schemas import Customer, CustomerRef, Issue, LineItem, OrderForm, ResidueSpan


def collect_residue(
    tokens: list[str],
    labels: list[str | None],
    spans: list[Span],
    consumed: set[int],
) -> list[ResidueSpan]:
    """Pass 5: Collect any token span not absorbed by line items or closed classes.

    Assigns adjacent_to_qty_or_unit and initial interpretation.
    """
    residue: list[ResidueSpan] = []
    num_tokens = len(tokens)

    i = 0
    while i < num_tokens:
        if i in consumed or labels[i] in (
            "FILLER",
            "GENITIVE",
            "HONORIFIC",
            "UDHAAR",
            "CASH",
            "CURRENCY",
            "QUERY",
            "NEGATION",
        ):
            i += 1
            continue

        # Found start of unconsumed span
        span_start = i
        while i < num_tokens and i not in consumed and labels[i] not in (
            "FILLER",
            "GENITIVE",
            "HONORIFIC",
            "UDHAAR",
            "CASH",
            "CURRENCY",
            "QUERY",
            "NEGATION",
        ):
            i += 1
        span_end = i

        span_tokens = tokens[span_start:span_end]
        text = " ".join(span_tokens).strip()
        if not text:
            continue

        # Check adjacency to QTY or UNIT
        adj_qty_or_unit = False
        if span_start > 0 and labels[span_start - 1] in ("QTY", "UNIT"):
            adj_qty_or_unit = True
        if span_end < num_tokens and labels[span_end] in ("QTY", "UNIT"):
            adj_qty_or_unit = True

        interpretation: str = "product" if adj_qty_or_unit else "customer"

        residue.append(
            ResidueSpan(
                text=text,
                token_span=(span_start, span_end),
                adjacent_to_qty_or_unit=adj_qty_or_unit,
                interpretation=interpretation,  # type: ignore[arg-type]
            )
        )

    return residue


def attribute_residue(
    residue: list[ResidueSpan],
    customer_spans: list[Span],
    line_items: list[LineItem],
    labels: list[str | None],
    customers: list[Customer],
    open_draft: str | None = None,
) -> tuple[CustomerRef, OrderForm, str, list[Issue]]:
    """Pass 6: Attribute customer and determine order_form and payment_type.

    Propagates Span.match_status into CustomerRef.status.
    Two or more isolated customer candidates -> blocking.
    Returns (customer, order_form, payment_type, issues).
    """
    issues: list[Issue] = []
    order_form: OrderForm = "canonical"

    # Gather customer candidates from Pass 3 spans and customer residue
    candidate_spans: list[tuple[int, int, str, str, float, str | None, list[str]]] = []
    # Each entry: (start, end, text, status, score, customer_id, candidate_ids)

    for c_span in customer_spans:
        candidate_spans.append(
            (
                c_span.start,
                c_span.end,
                c_span.raw_name,
                c_span.match_status,
                c_span.score,
                c_span.ref_id,
                c_span.candidates,
            )
        )

    # Also add isolated customer residue spans not already in candidate_spans
    for r in residue:
        if r.interpretation == "customer":
            # Check if this span is already covered by a customer span
            covered = any(
                c_start <= r.token_span[0] and r.token_span[1] <= c_end
                for c_start, c_end, *_ in candidate_spans
            )
            if not covered:
                m = match_customer(r.text, customers)
                candidate_spans.append(
                    (
                        r.token_span[0],
                        r.token_span[1],
                        r.text,
                        m.status,
                        m.score,
                        m.target_id,
                        m.candidates,
                    )
                )

    # Determine Payment Type
    has_cash_marker = any(lab == "CASH" for lab in labels)
    has_udhaar_marker = any(lab == "UDHAAR" for lab in labels)
    spoken_payment = "cash" if has_cash_marker else ("udhaar" if has_udhaar_marker else None)

    # Case: Two or more isolated customer candidates -> Blocking (Case 8 & docs/02 §3)
    if len(candidate_spans) >= 2:
        cust = CustomerRef(
            customer_id=None,
            raw_name=" / ".join(c[2] for c in candidate_spans),
            status="ambiguous",
            confidence=0.0,
            candidates=[c[5] for c in candidate_spans if c[5]],
            source="spoken",
        )
        issues.append(
            Issue(
                rule="V6",
                message="Two or more isolated customer candidates spoken; ambiguous.",
            )
        )
        payment_type = spoken_payment or "udhaar"
        # Relative position
        first_cust_start = min(c[0] for c in candidate_spans)
        if line_items:
            min_item = min(item.token_span[0] for item in line_items)
            order_form = "canonical" if first_cust_start < min_item else "name_last"
        else:
            order_form = "canonical"
        return cust, order_form, payment_type, issues

    # Case: Exactly one customer candidate
    if len(candidate_spans) == 1:
        c_start, c_end, text, status, score, c_id, cand_ids = candidate_spans[0]

        # Expand customer span to include adjacent honorifics and genitives for position check
        ext_start = c_start
        ext_end = c_end
        if ext_start > 0 and labels[ext_start - 1] in ("HONORIFIC", "GENITIVE"):
            ext_start -= 1
        if ext_end < len(labels) and labels[ext_end] in ("HONORIFIC", "GENITIVE"):
            ext_end += 1

        cust = CustomerRef(
            customer_id=c_id,
            raw_name=text,
            status="resolved" if status == "resolved" else ("ambiguous" if status == "ambiguous" else "unknown"),
            confidence=score / 100.0 if score else 0.0,
            candidates=cand_ids,
            source="spoken",
        )

        if status == "ambiguous":
            issues.append(
                Issue(
                    rule="V6",
                    message=f"Ambiguous customer '{text}'; candidates: {cand_ids}",
                )
            )

        # Determine order_form relative to line items
        if line_items:
            min_item_start = min(it.token_span[0] for it in line_items)
            max_item_end = max(it.token_span[1] for it in line_items)

            if ext_end <= min_item_start:
                order_form = "canonical"
            elif ext_start >= max_item_end:
                order_form = "name_last"
            else:
                order_form = "name_medial"
        else:
            order_form = "canonical"

        payment_type = spoken_payment or "udhaar"
        return cust, order_form, payment_type, issues

    # Case: No customer candidate at all (Case 4 & Case 5)
    if open_draft is not None:
        cust = CustomerRef(
            customer_id=open_draft,
            raw_name=None,
            status="resolved",
            confidence=1.0,
            candidates=[open_draft],
            source="open_draft",
        )
        order_form_draft: OrderForm = "no_name_draft"
        payment_type = spoken_payment or "udhaar"
        return cust, order_form_draft, payment_type, issues
    else:
        cust = CustomerRef(
            customer_id=None,
            raw_name=None,
            status="absent",
            confidence=1.0,
            candidates=[],
            source="cash_default",
        )
        order_form_cash: OrderForm = "no_name_cash"
        payment_type = spoken_payment or "cash"
        return cust, order_form_cash, payment_type, issues
