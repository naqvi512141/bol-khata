"""Tests using verbatim real-ASR transcript strings.

Groq whisper-large-v3 returns Urdu text with NO punctuation — no commas, no
Urdu commas. The local faster-whisper engine sometimes inserts one Urdu comma.
Phase 3 extractor tests all used pre-tokenized list[str] input, leaving the
raw-string (no-punctuation) path through _normalize_token_input untested.

These tests verify that punctuation presence or absence never changes the parse.
"""

from __future__ import annotations

import pytest

from app.extractor import extract
from app.schemas import Customer, SKU


# ── verbatim ASR strings ────────────────────────────────────────────────────

# Exact Groq transcript — zero punctuation
GROQ_VERBATIM = "احمد بھائی کا دو کلو چینی آدھا کلو بیسن"

# Same content with Urdu commas (manual / ideal punctuation)
WITH_URDU_COMMAS = "احمد بھائی کا، دو کلو چینی، آدھا کلو بیسن"

# Local engine variant: one Urdu comma between items, none after the name
LOCAL_ONE_COMMA = "احمد بھائی کا دو کلو چینی، آدھا کلو بیسن"

# With ASCII commas (defensive — shouldn't appear but let's be safe)
WITH_ASCII_COMMAS = "احمد بھائی کا, دو کلو چینی, آدھا کلو بیسن"


# ── helpers ──────────────────────────────────────────────────────────────────

def _item_signature(draft):
    """Canonical (sku_id, qty, unit) tuple list, sorted for comparison."""
    return sorted(
        (it.sku_id, it.qty, it.unit) for it in draft.items
    )


EXPECTED_SIGNATURE = [("SKU_001", 2.0, "kg"), ("SKU_006", 0.5, "kg")]


# ── test class ───────────────────────────────────────────────────────────────

class TestRealASRVerbatim:
    """Verbatim real-ASR transcripts must parse identically regardless of punctuation."""

    def test_groq_no_punctuation(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Test 1: Exact Groq output (no commas) parses correctly.

        Input: 'احمد بھائی کا دو کلو چینی آدھا کلو بیسن'
        Expected: customer=Ahmed, order_form=canonical, 2 items:
          (qty=2, kg, cheeni) and (qty=0.5, kg, besan).
        """
        draft = extract(GROQ_VERBATIM, catalogue, customers)

        assert draft.order_form == "canonical"
        assert draft.customer.status == "resolved"
        assert len(draft.items) == 2, (
            f"Expected exactly 2 line items, got {len(draft.items)}: "
            f"{[(it.sku_id, it.raw_name, it.qty, it.unit) for it in draft.items]}"
        )
        assert _item_signature(draft) == EXPECTED_SIGNATURE

    def test_with_urdu_commas(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Test 2: Same content WITH Urdu commas produces identical result."""
        draft = extract(WITH_URDU_COMMAS, catalogue, customers)

        assert draft.order_form == "canonical"
        assert draft.customer.status == "resolved"
        assert len(draft.items) == 2
        assert _item_signature(draft) == EXPECTED_SIGNATURE

    def test_local_engine_one_comma(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Test 3: Local engine variant with one Urdu comma produces identical result."""
        draft = extract(LOCAL_ONE_COMMA, catalogue, customers)

        assert draft.order_form == "canonical"
        assert draft.customer.status == "resolved"
        assert len(draft.items) == 2
        assert _item_signature(draft) == EXPECTED_SIGNATURE

    def test_with_ascii_commas(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Defensive: ASCII commas also produce identical result."""
        draft = extract(WITH_ASCII_COMMAS, catalogue, customers)

        assert draft.order_form == "canonical"
        assert draft.customer.status == "resolved"
        assert len(draft.items) == 2
        assert _item_signature(draft) == EXPECTED_SIGNATURE

    def test_punctuation_invariance(
        self, catalogue: list[SKU], customers: list[Customer]
    ) -> None:
        """Test 4: All punctuation variants produce IDENTICAL parses.

        Explicitly asserts that punctuation presence never changes
        order_form, customer, item count, or item details.
        """
        drafts = {
            "groq_no_punct": extract(GROQ_VERBATIM, catalogue, customers),
            "urdu_commas": extract(WITH_URDU_COMMAS, catalogue, customers),
            "local_one_comma": extract(LOCAL_ONE_COMMA, catalogue, customers),
            "ascii_commas": extract(WITH_ASCII_COMMAS, catalogue, customers),
        }

        sigs = {name: _item_signature(d) for name, d in drafts.items()}
        forms = {name: d.order_form for name, d in drafts.items()}
        custs = {name: d.customer.status for name, d in drafts.items()}
        cust_ids = {name: d.customer.customer_id for name, d in drafts.items()}

        # All item signatures must be identical
        sig_values = list(sigs.values())
        for name, sig in sigs.items():
            assert sig == sig_values[0], (
                f"Punctuation variant '{name}' produced different items: {sig} "
                f"vs baseline: {sig_values[0]}"
            )

        # All order_forms must be identical
        form_values = list(forms.values())
        for name, form in forms.items():
            assert form == form_values[0], (
                f"Punctuation variant '{name}' produced order_form='{form}' "
                f"vs baseline='{form_values[0]}'"
            )

        # All customer statuses must be identical
        cust_values = list(custs.values())
        for name, cust in custs.items():
            assert cust == cust_values[0], (
                f"Punctuation variant '{name}' produced customer status='{cust}' "
                f"vs baseline='{cust_values[0]}'"
            )

        # All customer IDs must be identical
        id_values = list(cust_ids.values())
        for name, cid in cust_ids.items():
            assert cid == id_values[0], (
                f"Punctuation variant '{name}' resolved customer_id='{cid}' "
                f"vs baseline='{id_values[0]}'"
            )

        # Final sanity: the shared result matches expectations
        assert sig_values[0] == EXPECTED_SIGNATURE
        assert form_values[0] == "canonical"
        assert cust_values[0] == "resolved"
