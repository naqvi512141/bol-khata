"""Tests for validation rules V1 through V7 and full validation gate.

Rules:
- V1: Stated total == sum(lines). Skipped when stated_total is None. (Blocking)
- V2: round(qty * unit_price) == line_total when all three present. (Blocking)
- V3: line_total within [0.6x, 1.7x] of SKU median * qty. (Warning)
      Skipped when fewer than 3 observations exist.
- V4: qty <= sku.max_plausible_qty. (Warning)
- V5: Every monetary value > 0 and an int. (Blocking)
- V6: customer.status == 'resolved' OR payment_type == 'cash'. (Blocking)
- V7: No line has price_source == 'missing'. (Blocking)
- requires_llm is False when the only blocking issues are V6 or V7.
"""

import pytest

from app.pricing.catalogue import Catalogue
from app.schemas import SKU, CustomerRef, LineItem
from app.validation.rules import (
    validate,
    validate_v1_total,
    validate_v2_line_arithmetic,
    validate_v3_price_plausibility,
    validate_v4_quantity_plausibility,
    validate_v5_positive_integer_money,
    validate_v6_customer_identity,
    validate_v7_missing_prices,
)


@pytest.fixture
def catalogue() -> Catalogue:
    skus = [
        SKU(
            sku_id="SKU_001",
            display_name="چینی",
            aliases=["cheeni"],
            default_unit="kg",
            unit_price=300,
            max_plausible_qty=25.0,
        ),
        SKU(
            sku_id="SKU_002",
            display_name="آٹا",
            aliases=["aata"],
            default_unit="kg",
            unit_price=140,
            max_plausible_qty=50.0,
        ),
    ]
    cat = Catalogue(skus)
    # Give SKU_001 3 historical observations around 300 PKR
    cat.observe_price("SKU_001", amount=300, qty=1.0)
    cat.observe_price("SKU_001", amount=300, qty=1.0)
    cat.observe_price("SKU_001", amount=300, qty=1.0)
    return cat


def make_clean_line_item() -> LineItem:
    return LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        qty=1.0,
        unit="kg",
        unit_price=300,
        line_total=300,
        price_source="catalogue",
        match_status="resolved",
        token_span=(0, 2),
    )


def make_clean_customer() -> CustomerRef:
    return CustomerRef(
        customer_id="CUST_001",
        raw_name="احمد",
        status="resolved",
        confidence=0.95,
        candidates=["احمد"],
        source="spoken",
    )


# ------------------ Clean Input Pass ------------------


def test_clean_input_passes_all_rules(catalogue: Catalogue) -> None:
    """A completely valid draft produces no blocking issues and passes."""
    items = [make_clean_line_item()]
    customer = make_clean_customer()
    result = validate(
        items=items,
        customer=customer,
        payment_type="udhaar",
        catalogue=catalogue,
        stated_total=300,
        computed_total=300,
    )

    assert result.passed is True
    assert len(result.blocking) == 0
    assert len(result.warnings) == 0
    assert result.requires_llm is False


# ------------------ V1: Total Mismatch ------------------


def test_v1_fails_on_total_mismatch() -> None:
    """V1 triggers a blocking issue when stated_total != sum(line_totals)."""
    items = [
        LineItem(
            sku_id="SKU_001",
            raw_name="چینی",
            line_total=300,
            match_status="resolved",
            token_span=(0, 1),
        ),
        LineItem(
            sku_id="SKU_002",
            raw_name="آٹا",
            line_total=140,
            match_status="resolved",
            token_span=(1, 2),
        ),
    ]
    # Sum is 440, but stated is 500
    issue = validate_v1_total(items, stated_total=500)
    assert issue is not None
    assert issue.rule == "V1"


def test_v1_passes_when_totals_match() -> None:
    """V1 passes when stated_total == sum(line_totals)."""
    items = [
        LineItem(
            sku_id="SKU_001",
            raw_name="چینی",
            line_total=300,
            match_status="resolved",
            token_span=(0, 1),
        ),
        LineItem(
            sku_id="SKU_002",
            raw_name="آٹا",
            line_total=140,
            match_status="resolved",
            token_span=(1, 2),
        ),
    ]
    assert validate_v1_total(items, stated_total=440) is None


def test_v1_skipped_when_stated_total_is_none() -> None:
    """V1 is SKIPPED when stated_total is None (most real utterances omit it)."""
    items = [
        LineItem(
            sku_id="SKU_001",
            raw_name="چینی",
            line_total=300,
            match_status="resolved",
            token_span=(0, 1),
        )
    ]
    # Must not fail or raise when stated_total is None
    assert validate_v1_total(items, stated_total=None) is None


# ------------------ V2: Line Arithmetic ------------------


def test_v2_fails_on_arithmetic_mismatch() -> None:
    """V2 triggers a blocking issue when round(qty * unit_price) != line_total."""
    # 2 kg * 100 PKR should be 200, but line_total is 250
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        qty=2.0,
        unit_price=100,
        line_total=250,
        match_status="resolved",
        token_span=(0, 2),
    )
    issue = validate_v2_line_arithmetic(item, item_index=0)
    assert issue is not None
    assert issue.rule == "V2"
    assert issue.item_index == 0


def test_v2_passes_when_arithmetic_matches() -> None:
    """V2 passes when round(qty * unit_price) == line_total."""
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        qty=2.5,
        unit_price=100,
        line_total=250,  # 2.5 * 100 = 250
        match_status="resolved",
        token_span=(0, 2),
    )
    assert validate_v2_line_arithmetic(item, item_index=0) is None


def test_v2_skipped_when_fields_missing() -> None:
    """V2 is skipped when not all three of qty, unit_price, line_total are present."""
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        qty=2.0,
        unit_price=None,
        line_total=200,
        match_status="resolved",
        token_span=(0, 2),
    )
    assert validate_v2_line_arithmetic(item) is None


# ------------------ V3: Price Plausibility ------------------


def test_v3_catches_10x_price_error(catalogue: Catalogue) -> None:
    """V3 catches a deliberate 10x price error (300 becomes 3000) and proves it fires."""
    # Historical median is 300 PKR for 1 kg.
    # 10x error: line_total is 3000 PKR instead of 300 PKR.
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        qty=1.0,
        unit="kg",
        unit_price=3000,
        line_total=3000,
        price_source="spoken",
        match_status="resolved",
        token_span=(0, 2),
    )

    issue = validate_v3_price_plausibility(item, catalogue, item_index=0)
    assert issue is not None
    assert issue.rule == "V3"
    assert issue.item_index == 0


def test_v3_passes_within_plausible_band(catalogue: Catalogue) -> None:
    """V3 passes when price is within [0.6x, 1.7x] of median."""
    # Median is 300. Plausible band for 1 kg is [180, 510].
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        qty=1.0,
        unit="kg",
        line_total=320,  # Within [180, 510]
        match_status="resolved",
        token_span=(0, 2),
    )
    assert validate_v3_price_plausibility(item, catalogue) is None


def test_v3_skipped_when_fewer_than_3_observations(catalogue: Catalogue) -> None:
    """V3 is SKIPPED when fewer than 3 price observations exist (SKU_002 has 0)."""
    # SKU_002 has no price history observations
    item = LineItem(
        sku_id="SKU_002",
        raw_name="آٹا",
        qty=1.0,
        unit="kg",
        line_total=5000,  # Wild price, but no baseline exists
        match_status="resolved",
        token_span=(0, 2),
    )
    # Must be skipped
    assert validate_v3_price_plausibility(item, catalogue) is None


# ------------------ V4: Plausible Quantity ------------------


def test_v4_fails_on_implausible_quantity(catalogue: Catalogue) -> None:
    """V4 triggers a warning issue when qty exceeds max_plausible_qty."""
    # SKU_001 max_plausible_qty is 25.0 kg
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        qty=100.0,
        unit="kg",
        match_status="resolved",
        token_span=(0, 2),
    )
    issue = validate_v4_quantity_plausibility(item, catalogue, item_index=0)
    assert issue is not None
    assert issue.rule == "V4"
    assert issue.item_index == 0


def test_v4_passes_within_plausible_quantity(catalogue: Catalogue) -> None:
    """V4 passes when qty <= max_plausible_qty."""
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        qty=5.0,
        unit="kg",
        match_status="resolved",
        token_span=(0, 2),
    )
    assert validate_v4_quantity_plausibility(item, catalogue) is None


# ------------------ V5: Positive Integer Money ------------------


def test_v5_fails_on_zero_or_negative_money() -> None:
    """V5 triggers a blocking issue when monetary values are <= 0."""
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        line_total=0,  # Zero PKR
        match_status="resolved",
        token_span=(0, 1),
    )
    issues = validate_v5_positive_integer_money([item])
    assert len(issues) > 0
    assert any(i.rule == "V5" for i in issues)

    item_neg = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        line_total=-50,  # Negative PKR
        match_status="resolved",
        token_span=(0, 1),
    )
    issues_neg = validate_v5_positive_integer_money([item_neg])
    assert len(issues_neg) > 0
    assert any(i.rule == "V5" for i in issues_neg)


def test_v5_fails_on_float_money() -> None:
    """V5 triggers a blocking issue when money is float (AGENTS.md rule 1)."""
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        line_total=100,
        match_status="resolved",
        token_span=(0, 1),
    )
    # If stated_total is a float
    issues = validate_v5_positive_integer_money([item], stated_total=100.5)  # type: ignore[arg-type]
    assert len(issues) > 0
    assert any(i.rule == "V5" for i in issues)


# ------------------ V6: Customer Disambiguation ------------------


def test_v6_fails_on_ambiguous_customer_for_udhaar() -> None:
    """V6 blocks an udhaar (credit) transaction when customer status is not resolved."""
    customer = CustomerRef(
        customer_id=None,
        raw_name="احمد",
        status="ambiguous",  # Ambiguous customer
        confidence=0.5,
        candidates=["احمد بھائی", "احمد خان"],
        source="spoken",
    )
    issue = validate_v6_customer_identity(customer, payment_type="udhaar")
    assert issue is not None
    assert issue.rule == "V6"


def test_v6_passes_for_resolved_customer() -> None:
    """V6 passes for udhaar when customer is resolved."""
    customer = make_clean_customer()
    assert validate_v6_customer_identity(customer, payment_type="udhaar") is None


def test_v6_passes_for_cash_sale_even_without_customer() -> None:
    """V6 passes for cash sales even when customer is absent or unknown."""
    customer = CustomerRef(status="absent", source="cash_default")
    assert validate_v6_customer_identity(customer, payment_type="cash") is None


# ------------------ V7: Missing Prices ------------------


def test_v7_fails_when_item_price_is_missing() -> None:
    """V7 triggers a blocking issue when price_source is 'missing' or line_total is None."""
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        price_source="missing",
        line_total=None,
        match_status="resolved",
        token_span=(0, 1),
    )
    issues = validate_v7_missing_prices([item])
    assert len(issues) == 1
    assert issues[0].rule == "V7"
    assert issues[0].item_index == 0


def test_v7_passes_when_all_prices_present() -> None:
    """V7 passes when all items have price_source != 'missing' and line_total set."""
    item = make_clean_line_item()
    assert len(validate_v7_missing_prices([item])) == 0


# ------------------ requires_llm Logic ------------------


def test_requires_llm_false_when_only_v6_blocks(catalogue: Catalogue) -> None:
    """requires_llm is False when the only blocking issue is V6 (customer)."""
    items = [make_clean_line_item()]
    ambiguous_customer = CustomerRef(
        status="ambiguous",
        confidence=0.5,
        source="spoken",
    )
    result = validate(
        items=items,
        customer=ambiguous_customer,
        payment_type="udhaar",
        catalogue=catalogue,
        stated_total=300,
        computed_total=300,
    )

    assert result.passed is False
    assert len(result.blocking) == 1
    assert result.blocking[0].rule == "V6"
    assert result.requires_llm is False  # Needs a human shopkeeper, not an LLM


def test_requires_llm_false_when_only_v7_blocks(catalogue: Catalogue) -> None:
    """requires_llm is False when the only blocking issue is V7 (missing price)."""
    unpriced_item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        price_source="missing",
        line_total=None,
        match_status="resolved",
        token_span=(0, 1),
    )
    customer = make_clean_customer()
    result = validate(
        items=[unpriced_item],
        customer=customer,
        payment_type="udhaar",
        catalogue=catalogue,
        stated_total=None,
        computed_total=None,
    )

    assert result.passed is False
    assert any(i.rule == "V7" for i in result.blocking)
    # The only blocking issue is V7
    assert all(i.rule == "V7" for i in result.blocking)
    assert result.requires_llm is False  # Needs human to speak/enter price


def test_requires_llm_true_for_arithmetic_or_total_mismatch(catalogue: Catalogue) -> None:
    """requires_llm is True when blocking issues are V1, V2, or V5 (reparable by LLM)."""
    items = [make_clean_line_item()]
    customer = make_clean_customer()
    # Stated total mismatch triggers V1
    result = validate(
        items=items,
        customer=customer,
        payment_type="udhaar",
        catalogue=catalogue,
        stated_total=999,  # Doesn't match 300
        computed_total=300,
    )

    assert result.passed is False
    assert len(result.blocking) == 1
    assert result.blocking[0].rule == "V1"
    assert result.requires_llm is True
