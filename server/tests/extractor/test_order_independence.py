"""Tests for order-independent extraction.

Per docs/01-domain-urdu.md §8 (Extractor table) and docs/02-contracts.md §3.
Authoritative test suite: All 10 cases from the extractor table.
"""

from __future__ import annotations

import pytest

from app.extractor import extract
from app.schemas import Customer, SKU


class TestExtractorTableCases:
    """The 10 authoritative test cases from docs/01-domain-urdu.md §8."""

    def test_canonical_order(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Case 1: 'Ahmed bhai ka, do kilo cheeni, aadha kilo besan'

        Expected: customer=Ahmed, 2 items, order_form=canonical, payment_type=udhaar.
        """
        text = "احمد بھائی کا، دو کلو چینی، آدھا کلو بیسن"
        tokens = ["احمد", "بھائی", "کا", "دو", "کلو", "چینی", "آدھا", "کلو", "بیسن"]
        draft = extract(tokens, catalogue, customers)

        assert draft.order_form == "canonical"
        assert draft.customer.status == "resolved"
        assert draft.customer.customer_id in ("CUST_001", "CUST_003")
        assert draft.payment_type == "udhaar"
        assert len(draft.items) == 2

        # Check line items
        items_by_sku = {item.sku_id: item for item in draft.items}
        assert "SKU_001" in items_by_sku  # cheeni
        assert items_by_sku["SKU_001"].qty == pytest.approx(2.0)
        assert items_by_sku["SKU_001"].unit == "kg"

        assert "SKU_006" in items_by_sku  # besan
        assert items_by_sku["SKU_006"].qty == pytest.approx(0.5)
        assert items_by_sku["SKU_006"].unit == "kg"

    def test_name_last_order(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Case 2: 'do kilo cheeni, aadha kilo besan, Ahmed bhai'

        Expected: customer=Ahmed, 2 items, order_form=name_last.
        """
        tokens = ["دو", "کلو", "چینی", "آدھا", "کلو", "بیسن", "احمد", "بھائی"]
        draft = extract(tokens, catalogue, customers)

        assert draft.order_form == "name_last"
        assert draft.customer.status == "resolved"
        assert draft.customer.customer_id in ("CUST_001", "CUST_003")
        assert draft.payment_type == "udhaar"
        assert len(draft.items) == 2

    def test_name_medial_order(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Case 3: 'do kilo cheeni, Ahmed bhai ka, aadha kilo besan'

        Expected: customer=Ahmed, 2 items, order_form=name_medial.
        """
        tokens = ["دو", "کلو", "چینی", "احمد", "بھائی", "کا", "آدھا", "کلو", "بیسن"]
        draft = extract(tokens, catalogue, customers)

        assert draft.order_form == "name_medial"
        assert draft.customer.status == "resolved"
        assert draft.customer.customer_id in ("CUST_001", "CUST_003")
        assert draft.payment_type == "udhaar"
        assert len(draft.items) == 2

    def test_no_name_draft_open(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Case 4: 'do kilo cheeni, aadha kilo besan' with open draft.

        Expected: customer from draft, payment_type=udhaar, order_form=no_name_draft.
        """
        tokens = ["دو", "کلو", "چینی", "آدھا", "کلو", "بیسن"]
        open_draft_cust_id = "CUST_004"
        draft = extract(tokens, catalogue, customers, open_draft=open_draft_cust_id)

        assert draft.order_form == "no_name_draft"
        assert draft.customer.customer_id == open_draft_cust_id
        assert draft.customer.source == "open_draft"
        assert draft.payment_type == "udhaar"
        assert len(draft.items) == 2

    def test_no_name_cash(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Case 5: 'do kilo cheeni, aadha kilo besan' with no draft open.

        Expected: customer absent, payment_type=cash, order_form=no_name_cash.
        """
        tokens = ["دو", "کلو", "چینی", "آدھا", "کلو", "بیسن"]
        draft = extract(tokens, catalogue, customers, open_draft=None)

        assert draft.order_form == "no_name_cash"
        assert draft.customer.customer_id is None
        assert draft.customer.status == "absent"
        assert draft.customer.source == "cash_default"
        assert draft.payment_type == "cash"
        assert len(draft.items) == 2

    def test_central_order_independence_identical_items(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Central test: The same basket in four word orders must produce IDENTICAL items.

        AGENTS.md rule 6 & docs/01 §8.
        """
        order_canonical = ["احمد", "بھائی", "کا", "دو", "کلو", "چینی", "آدھا", "کلو", "بیسن"]
        order_last = ["دو", "کلو", "چینی", "آدھا", "کلو", "بیسن", "احمد", "بھائی"]
        order_medial = ["دو", "کلو", "چینی", "احمد", "بھائی", "کا", "آدھا", "کلو", "بیسن"]
        order_no_name = ["دو", "کلو", "چینی", "آدھا", "کلو", "بیسن"]

        draft1 = extract(order_canonical, catalogue, customers)
        draft2 = extract(order_last, catalogue, customers)
        draft3 = extract(order_medial, catalogue, customers)
        draft4 = extract(order_no_name, catalogue, customers, open_draft="DRAFT_001")

        # Compare items across all four
        def item_signature(items: list) -> list[tuple[str | None, float | None, str | None]]:
            return sorted(
                (it.sku_id, it.qty, it.unit) for it in items
            )

        sig1 = item_signature(draft1.items)
        sig2 = item_signature(draft2.items)
        sig3 = item_signature(draft3.items)
        sig4 = item_signature(draft4.items)

        assert sig1 == sig2 == sig3 == sig4
        assert sig1 == [("SKU_001", 2.0, "kg"), ("SKU_006", 0.5, "kg")]

    def test_multi_token_sku_aik_paw_laal_mirch(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Case 6: 'aik paw laal mirch'

        Expected: ONE item ('laal mirch'), not two items.
        AGENTS.md rule 7: SKU matching is n-gram, longest-span-first.
        """
        tokens = ["ایک", "پاؤ", "لال", "مرچ"]
        draft = extract(tokens, catalogue, customers)

        assert len(draft.items) == 1, "laal mirch must be recognized as a single SKU, not two items"
        item = draft.items[0]
        assert item.sku_id == "SKU_007"  # laal mirch
        assert item.qty == pytest.approx(0.25)
        assert item.unit == "kg"

    def test_paw_bottle_ambiguous_blocking(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Case 7: 'paw bottle' (SKU default_unit is not mass)

        docs/01 §5 & §8: paw with non-mass unit is ambiguous -> blocking.
        """
        # "کولا" (cola) default unit is "bottle"
        tokens = ["پاؤ", "کولا"]
        draft = extract(tokens, catalogue, customers)

        # Must have a blocking validation issue
        assert len(draft.validation.blocking) > 0 or draft.validation.passed is False

    def test_two_isolated_residue_spans_blocking(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Case 8: 'do kilo cheeni, Ahmed bhai, Bilal bhai'

        Two isolated residue spans -> BLOCKING. Never guess which is customer.
        docs/02 §3 residue table & docs/01 §8.
        """
        tokens = ["دو", "کلو", "چینی", "احمد", "بھائی", "بلال", "بھائی"]
        draft = extract(tokens, catalogue, customers)

        assert (
            len(draft.validation.blocking) > 0
            or draft.customer.status == "ambiguous"
            or not draft.validation.passed
        )

    def test_unknown_word_adjacent_to_qty_is_provisional_sku(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Case 9: Unknown word adjacent to a qty -> provisional SKU, NOT a customer.

        docs/02 §3 residue table & docs/01 §8.
        """
        # "کھویا" is not in the catalogue
        tokens = ["دو", "کلو", "کھویا"]
        draft = extract(tokens, catalogue, customers)

        # Must be treated as a provisional product, not attributed to customer
        assert len(draft.items) == 1
        item = draft.items[0]
        assert item.match_status == "provisional"
        assert "کھویا" in item.raw_name
        assert draft.customer.status == "absent"

    def test_unknown_word_isolated_is_new_customer_candidate(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Case 10: Unknown word isolated -> new-customer candidate.

        docs/02 §3 residue table & docs/01 §8.
        """
        # "کامران" is not in customers.json, followed by genitive "کا"
        tokens = ["کامران", "کا", "دو", "کلو", "چینی"]
        draft = extract(tokens, catalogue, customers)

        assert draft.customer.status == "unknown"
        assert draft.customer.raw_name is not None
        assert "کامران" in draft.customer.raw_name
        assert len(draft.items) == 1
        assert draft.items[0].sku_id == "SKU_001"
