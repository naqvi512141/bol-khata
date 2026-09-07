"""Validation rules V1–V7 for credit ledger entries.

Docs: docs/02-contracts.md §7; docs/03-build-plan.md Phase 4.

Rules:
- V1: sum(line_totals) == stated_total. Skipped when stated_total is None. (Severity: Blocking)
- V2: round(qty * unit_price) == line_total when all three present. (Severity: Blocking)
- V3: line_total within [0.6x, 1.7x] of SKU median * qty. (Severity: Warning)
      Skipped when fewer than 3 observations exist.
- V4: qty <= sku.max_plausible_qty. (Severity: Warning)
- V5: Every monetary value > 0 and an int. (Severity: Blocking)
- V6: customer.status == 'resolved' OR payment_type == 'cash'. (Severity: Blocking)
- V7: No line has price_source == 'missing'. (Severity: Blocking)
"""

from __future__ import annotations

from collections.abc import Sequence

from app.pricing.catalogue import Catalogue
from app.schemas import CustomerRef, Issue, LineItem, ParsedDraft, ValidationResult


def validate_v1_total(items: Sequence[LineItem], stated_total: int | None) -> Issue | None:
    """V1: sum(line_totals) == stated_total.

    SKIPPED when stated_total is None (AGENTS.md & prompt rules).
    Severity: Blocking.
    """
    if stated_total is None:
        return None

    # Compute sum of line totals (int PKR)
    sum_lines = sum(item.line_total for item in items if item.line_total is not None)
    if sum_lines != stated_total:
        return Issue(
            rule="V1",
            item_index=None,
            message=(
                f"Stated total PKR {stated_total} does not match computed sum PKR {sum_lines}"
            ),
        )
    return None


def validate_v2_line_arithmetic(item: LineItem, item_index: int | None = None) -> Issue | None:
    """V2: round(qty * unit_price) == line_total when all three present.

    Severity: Blocking.
    """
    if item.qty is not None and item.unit_price is not None and item.line_total is not None:
        expected = round(item.qty * item.unit_price)
        if expected != item.line_total:
            return Issue(
                rule="V2",
                item_index=item_index,
                message=(
                    f"Line item arithmetic mismatch: qty {item.qty} * "
                    f"unit_price {item.unit_price} = PKR {expected} != line_total PKR {item.line_total}"
                ),
            )
    return None


def validate_v3_price_plausibility(
    item: LineItem,
    catalogue: Catalogue,
    item_index: int | None = None,
) -> Issue | None:
    """V3: line_total within [0.6x, 1.7x] of SKU median * qty.

    Skipped when fewer than 3 observations exist (median_price returns None).
    Severity: Warning.
    """
    if item.sku_id is None or item.line_total is None:
        return None

    median = catalogue.median_price(item.sku_id)
    if median is None:
        # Skipped when fewer than 3 price observations exist
        return None

    qty = item.qty if (item.qty is not None and item.qty > 0) else 1.0
    expected = median * qty
    low_bound = 0.6 * expected
    high_bound = 1.7 * expected

    if item.line_total < low_bound or item.line_total > high_bound:
        return Issue(
            rule="V3",
            item_index=item_index,
            message=(
                f"Line total PKR {item.line_total} is outside plausible range "
                f"[{low_bound:.1f}, {high_bound:.1f}] based on median unit price PKR {median}"
            ),
        )
    return None


def validate_v4_quantity_plausibility(
    item: LineItem,
    catalogue: Catalogue,
    item_index: int | None = None,
) -> Issue | None:
    """V4: qty <= sku.max_plausible_qty.

    Severity: Warning.
    """
    if item.sku_id is None or item.qty is None:
        return None

    sku = catalogue.get_sku(item.sku_id)
    if sku is None:
        return None

    if item.qty > sku.max_plausible_qty:
        return Issue(
            rule="V4",
            item_index=item_index,
            message=(
                f"Quantity {item.qty} exceeds max plausible quantity "
                f"{sku.max_plausible_qty} for SKU {item.sku_id}"
            ),
        )
    return None


def validate_v5_positive_integer_money(
    items: Sequence[LineItem],
    stated_total: int | None = None,
    computed_total: int | None = None,
) -> list[Issue]:
    """V5: Every monetary value > 0 and an int.

    Severity: Blocking.
    """
    issues: list[Issue] = []

    def _check_money(val: object, name: str, idx: int | None) -> None:
        if val is None:
            return
        # Must be int, not bool (bool is a subclass of int in Python), and > 0
        if type(val) is not int or val <= 0:
            issues.append(
                Issue(
                    rule="V5",
                    item_index=idx,
                    message=f"{name} ({val}) must be a positive integer PKR",
                )
            )

    _check_money(stated_total, "stated_total", None)
    _check_money(computed_total, "computed_total", None)

    for idx, item in enumerate(items):
        _check_money(item.spoken_amount, f"Item {idx} spoken_amount", idx)
        _check_money(item.unit_price, f"Item {idx} unit_price", idx)
        _check_money(item.line_total, f"Item {idx} line_total", idx)

    return issues


def validate_v6_customer_identity(
    customer: CustomerRef,
    payment_type: str,
) -> Issue | None:
    """V6: customer.status == 'resolved' OR payment_type == 'cash'.

    Severity: Blocking.
    """
    if customer.status == "resolved" or payment_type == "cash":
        return None

    return Issue(
        rule="V6",
        item_index=None,
        message=(
            f"Customer status '{customer.status}' is not resolved for {payment_type} sale. "
            "Credit sales require a resolved customer."
        ),
    )


def validate_v7_missing_prices(items: Sequence[LineItem]) -> list[Issue]:
    """V7: No line has price_source == 'missing'.

    Severity: Blocking.
    """
    issues: list[Issue] = []
    for idx, item in enumerate(items):
        if item.price_source == "missing" or item.line_total is None:
            issues.append(
                Issue(
                    rule="V7",
                    item_index=idx,
                    message=f"Line item {idx} ('{item.raw_name}') has missing price",
                )
            )
    return issues


def validate(
    items: Sequence[LineItem],
    customer: CustomerRef,
    payment_type: str,
    catalogue: Catalogue,
    stated_total: int | None = None,
    computed_total: int | None = None,
) -> ValidationResult:
    """Run all validation rules V1 through V7.

    Returns ValidationResult with:
    - passed: True if no blocking issues
    - blocking: list of blocking Issues (V1, V2, V5, V6, V7)
    - warnings: list of warning Issues (V3, V4)
    - requires_llm: True when there is at least one blocking issue and none of them is V6 or V7.
    """
    blocking: list[Issue] = []
    warnings: list[Issue] = []

    # V1: Total check (blocking)
    v1_issue = validate_v1_total(items, stated_total)
    if v1_issue:
        blocking.append(v1_issue)

    # V2: Line arithmetic (blocking)
    for idx, item in enumerate(items):
        v2_issue = validate_v2_line_arithmetic(item, idx)
        if v2_issue:
            blocking.append(v2_issue)

    # V3: Price plausibility (warning)
    for idx, item in enumerate(items):
        v3_issue = validate_v3_price_plausibility(item, catalogue, idx)
        if v3_issue:
            warnings.append(v3_issue)

    # V4: Quantity plausibility (warning)
    for idx, item in enumerate(items):
        v4_issue = validate_v4_quantity_plausibility(item, catalogue, idx)
        if v4_issue:
            warnings.append(v4_issue)

    # V5: Positive integer money (blocking)
    blocking.extend(
        validate_v5_positive_integer_money(items, stated_total, computed_total)
    )

    # V6: Customer identity (blocking)
    v6_issue = validate_v6_customer_identity(customer, payment_type)
    if v6_issue:
        blocking.append(v6_issue)

    # V7: Missing prices (blocking)
    blocking.extend(validate_v7_missing_prices(items))

    passed = len(blocking) == 0

    # requires_llm rule:
    # "requires_llm is True when there is at least one blocking issue and none of them is V6 or V7"
    # "requires_llm is False when the only blocking issues are V6 or V7. Those need a human, not a model."
    requires_llm = bool(blocking) and all(i.rule not in ("V6", "V7") for i in blocking)

    return ValidationResult(
        passed=passed,
        blocking=blocking,
        warnings=warnings,
        requires_llm=requires_llm,
    )


def validate_draft(draft: ParsedDraft, catalogue: Catalogue) -> ValidationResult:
    """Validate a complete ParsedDraft."""
    return validate(
        items=draft.items,
        customer=draft.customer,
        payment_type=draft.payment_type,
        catalogue=catalogue,
        stated_total=draft.stated_total,
        computed_total=draft.computed_total,
    )
