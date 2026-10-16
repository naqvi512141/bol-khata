"""Tests for server/app/llm/repair.py.

Contract:
- temperature 0, JSON mode, strip markdown code fences regardless,
  validate with Pydantic, one retry with the validation error appended,
  then set path="manual" and give up.
- LLM output is re-run through the FULL validation gate. It never bypasses it.
- Never let a model decide a monetary value alone (AGENTS.md rule 2).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.llm.repair import (
    _build_repair_prompt,
    _parse_llm_response,
    _strip_code_fences,
    llm_repair,
)
from app.schemas import (
    CustomerRef,
    Issue,
    LineItem,
    ParsedDraft,
    ValidationResult,
)


def _make_dummy_draft(
    items: list[LineItem] | None = None,
    requires_llm: bool = True,
    blocking_rules: list[str] | None = None,
) -> ParsedDraft:
    """Helper to create a test draft."""
    if items is None:
        items = [
            LineItem(
                sku_id="SKU_001",
                raw_name="چینی",
                display_name="Cheeni (Sugar)",
                qty=2.0,
                unit="kg",
                spoken_amount=None,
                unit_price=180,
                line_total=350,  # 2 * 180 = 360, deliberate mismatch for V2
                price_source="catalogue",
                match_score=100.0,
                match_status="resolved",
                candidates=["SKU_001"],
                derived_fields=["line_total"],
                token_span=(0, 2),
            )
        ]
    blocking_issues = [
        Issue(rule=rule, item_index=0, message=f"Error {rule}")
        for rule in (blocking_rules or ["V2"])
    ]
    return ParsedDraft(
        draft_id="d_test_repair",
        job_ids=["j_001"],
        shop_id="demo_shop_01",
        customer=CustomerRef(
            customer_id="CUST_001",
            raw_name="احمد",
            status="resolved",
            confidence=1.0,
            candidates=["CUST_001"],
            source="spoken",
        ),
        items=items,
        residue=[],
        stated_total=360,
        computed_total=350,
        payment_type="udhaar",
        currency="PKR",
        order_form="canonical",
        confidence=0.8,
        path="manual",
        validation=ValidationResult(
            passed=False,
            blocking=blocking_issues,
            warnings=[],
            requires_llm=requires_llm,
        ),
        normalized_tokens="احمد دو کلو چینی",
        raw_texts=["احمد دو کلو چینی"],
    )


# ==================== Code fence stripping ====================


def test_strip_code_fences_with_json_fence() -> None:
    text = '```json\n{"items": [], "computed_total": 0}\n```'
    assert _strip_code_fences(text) == '{"items": [], "computed_total": 0}'


def test_strip_code_fences_with_generic_fence() -> None:
    text = '```\n{"items": []}\n```'
    assert _strip_code_fences(text) == '{"items": []}'


def test_strip_code_fences_plain_text() -> None:
    text = '{"items": []}'
    assert _strip_code_fences(text) == '{"items": []}'


# ==================== Prompt construction ====================


def test_build_repair_prompt_structure() -> None:
    draft = _make_dummy_draft()
    messages = _build_repair_prompt(draft)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "Pakistani kiryana" in messages[0]["content"]
    assert "positive integers (PKR)" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "V2" in messages[1]["content"]


# ==================== LLM response parsing ====================


def test_parse_llm_response_valid() -> None:
    draft = _make_dummy_draft()
    item_payload = draft.items[0].model_dump(mode="json")
    item_payload["line_total"] = 360  # fixed
    raw = json.dumps({"items": [item_payload], "computed_total": 360})
    parsed = _parse_llm_response(raw, draft.items)
    assert len(parsed) == 1
    assert parsed[0].line_total == 360


def test_parse_llm_response_rejects_empty_items() -> None:
    with pytest.raises(ValueError, match="empty items list"):
        _parse_llm_response(json.dumps({"items": []}), [])


def test_parse_llm_response_rejects_float_money() -> None:
    draft = _make_dummy_draft()
    item_payload = draft.items[0].model_dump(mode="json")
    item_payload["line_total"] = 360.50  # float is invalid per AGENTS.md rule 1
    raw = json.dumps({"items": [item_payload]})
    # Pydantic v2 strict/coercion: float with decimal part fails int validation
    with pytest.raises(Exception):
        _parse_llm_response(raw, draft.items)


# ==================== llm_repair flow ====================


def test_llm_repair_success_attempt_1() -> None:
    draft = _make_dummy_draft()
    item_payload = draft.items[0].model_dump(mode="json")
    item_payload["line_total"] = 360
    llm_resp = json.dumps({"items": [item_payload], "computed_total": 360})

    mock_provider = MagicMock()
    mock_provider.chat.return_value = f"```json\n{llm_resp}\n```"

    repaired, computed_total, success = llm_repair(draft, mock_provider)
    assert success is True
    assert len(repaired) == 1
    assert repaired[0].line_total == 360
    assert computed_total == 360
    assert mock_provider.chat.call_count == 1


def test_llm_repair_retry_on_first_failure() -> None:
    draft = _make_dummy_draft()
    item_payload = draft.items[0].model_dump(mode="json")
    item_payload["line_total"] = 360
    valid_resp = json.dumps({"items": [item_payload], "computed_total": 360})

    mock_provider = MagicMock()
    # First call returns malformed JSON; second call returns valid JSON
    mock_provider.chat.side_effect = ["Invalid json {{{", valid_resp]

    repaired, computed_total, success = llm_repair(draft, mock_provider)
    assert success is True
    assert computed_total == 360
    assert mock_provider.chat.call_count == 2
    # Verify the retry prompt includes the error
    second_call_messages = mock_provider.chat.call_args_list[1][0][0]
    assert any("previous response had a validation error" in m["content"] for m in second_call_messages)


def test_llm_repair_fails_after_two_attempts() -> None:
    draft = _make_dummy_draft()

    mock_provider = MagicMock()
    mock_provider.chat.side_effect = ["bad json 1", "bad json 2"]

    repaired, computed_total, success = llm_repair(draft, mock_provider)
    assert success is False
    assert mock_provider.chat.call_count == 2
    # Returns original items and total
    assert len(repaired) == len(draft.items)
    assert computed_total == draft.computed_total
