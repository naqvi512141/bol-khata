"""LLM repair — invoked ONLY when validation.requires_llm is True.

Contract:
- temperature 0, JSON mode, strip markdown code fences regardless,
  validate with Pydantic, one retry with the validation error appended,
  then set path="manual" and give up.
- LLM output is re-run through the FULL validation gate. It never bypasses it.
- An LLM is NEVER called to decide a monetary value alone (AGENTS.md rule 2);
  we provide the existing draft as context and ask for structural repair.
"""

from __future__ import annotations

import json
import logging
import re

from app.llm.providers import LLMProvider
from app.schemas import LineItem, ParsedDraft

logger = logging.getLogger(__name__)

# Regex to strip markdown code fences (```json ... ```) from LLM output
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences, returning the inner content."""
    match = _CODE_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _build_repair_prompt(draft: ParsedDraft) -> list[dict[str, str]]:
    """Build the chat messages for an LLM repair attempt."""
    # Serialize the draft for context (exclude heavy fields)
    draft_dict = draft.model_dump(mode="json")
    # Remove fields the LLM doesn't need
    for key in ("residue", "normalized_tokens", "raw_texts"):
        draft_dict.pop(key, None)

    system_msg = (
        "You are a structured data repair assistant for a Pakistani kiryana shop ledger. "
        "You will receive a ParsedDraft JSON object that has validation errors. "
        "Your job is to fix the structural issues (mismatched totals, arithmetic errors) "
        "while preserving the original customer, items, and quantities as closely as possible.\n\n"
        "Rules:\n"
        "1. All monetary values (spoken_amount, unit_price, line_total, computed_total) "
        "must be positive integers (PKR). NEVER use float for money.\n"
        "2. Quantities (qty) are float.\n"
        "3. computed_total must equal the sum of all line_total values.\n"
        "4. If stated_total is present, the sum of line_totals must equal it.\n"
        "5. Do NOT invent new items. Only fix arithmetic and pricing.\n"
        "6. Return ONLY a JSON object with 'items' (list of LineItem objects) and "
        "'computed_total' (int). No other keys.\n"
        "7. Each item in 'items' must have: sku_id, raw_name, display_name, qty, unit, "
        "spoken_amount, unit_price, line_total, price_source, match_score, match_status, "
        "candidates, derived_fields, token_span."
    )

    user_msg = (
        f"The following ParsedDraft has validation errors:\n\n"
        f"Validation issues: {json.dumps([i.model_dump() for i in draft.validation.blocking], ensure_ascii=False)}\n\n"
        f"Draft:\n{json.dumps(draft_dict, ensure_ascii=False, indent=2)}\n\n"
        "Fix the issues and return the corrected JSON."
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def _parse_llm_response(raw_text: str, original_items: list[LineItem]) -> list[LineItem]:
    """Parse the LLM response into a list of LineItems.

    Raises ValueError on parse failure.
    """
    cleaned = _strip_code_fences(raw_text)
    data = json.loads(cleaned)

    if isinstance(data, dict):
        items_data = data.get("items", [])
    elif isinstance(data, list):
        items_data = data
    else:
        raise ValueError(f"Unexpected LLM response type: {type(data).__name__}")

    if not items_data:
        raise ValueError("LLM returned empty items list")

    repaired_items: list[LineItem] = []
    for i, item_dict in enumerate(items_data):
        # Ensure token_span is a tuple
        if "token_span" in item_dict and isinstance(item_dict["token_span"], list):
            item_dict["token_span"] = tuple(item_dict["token_span"])
        # Validate with Pydantic — this enforces all type constraints including
        # int for money fields (AGENTS.md rule 1)
        repaired_items.append(LineItem(**item_dict))

    return repaired_items


def llm_repair(
    draft: ParsedDraft,
    provider: LLMProvider,
) -> tuple[list[LineItem], int, bool]:
    """Attempt LLM repair of a draft with validation failures.

    Returns:
        (repaired_items, computed_total, success)
        - success=True if LLM produced valid items
        - success=False means path should be set to "manual"
    """
    messages = _build_repair_prompt(draft)

    raw_response = ""

    # Attempt 1
    try:
        raw_response = provider.chat(messages)
        repaired_items = _parse_llm_response(raw_response, draft.items)
        computed_total = sum(
            item.line_total for item in repaired_items if item.line_total is not None
        )
        return repaired_items, int(computed_total), True
    except Exception as first_err:
        logger.warning("LLM repair attempt 1 failed: %s", first_err)

        # Attempt 2 — append the error and retry once
        messages.append({
            "role": "assistant",
            "content": raw_response,
        })
        messages.append({
            "role": "user",
            "content": (
                f"Your previous response had a validation error:\n{first_err}\n\n"
                "Please fix it and return valid JSON."
            ),
        })

        try:
            raw_response_2 = provider.chat(messages)
            repaired_items = _parse_llm_response(raw_response_2, draft.items)
            computed_total = sum(
                item.line_total for item in repaired_items if item.line_total is not None
            )
            return repaired_items, int(computed_total), True
        except Exception as second_err:
            logger.warning("LLM repair attempt 2 failed: %s — giving up, path=manual", second_err)
            return list(draft.items), draft.computed_total, False
