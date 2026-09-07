"""Adjacency-based line-item grouping.

Per docs/02-contracts.md §3 (Pass 4), docs/01-domain-urdu.md §5 (paw disambiguation).
"""

from __future__ import annotations

from typing import cast

from app.extractor.ngram import Span
from app.normalizer.folding import urdu_fold
from app.normalizer.numbers import CARDINALS, parse_number_words
from app.normalizer.quantifiers import MODIFIER, STANDALONE, resolve_quantifier
from app.normalizer.units import resolve_unit
from app.schemas import SKU, Issue, LineItem, Unit

_PAW_FOLDED = urdu_fold("پاؤ")


def _parse_cluster_qty(
    tokens: list[str],
    cluster_indices: list[int],
) -> tuple[float | None, str | None]:
    """Parse quantity and optional unit hint from QTY tokens in the cluster."""
    for idx in cluster_indices:
        word = tokens[idx]
        # Check standalone or modifier quantifiers
        if word in STANDALONE or word in MODIFIER:
            qty, hint = resolve_quantifier(tokens, idx)
            if qty is not None:
                return qty, hint
        # Check cardinals or digits
        if word in CARDINALS or word.isdigit():
            val = parse_number_words([word])
            if val is not None:
                return float(val), None
            if word.isdigit():
                return float(word), None

    return None, None


def group_line_items(
    tokens: list[str],
    labels: list[str | None],
    item_spans: list[Span],
    catalogue: list[SKU],
    raw_tokens: list[str] | None = None,
) -> tuple[list[LineItem], set[int], list[Issue]]:
    """Pass 4: Group adjacent QTY, UNIT, ITEM, MONEY tokens into line items.

    Also detects provisional items (unknown word adjacent to QTY/UNIT).
    Returns (line_items, consumed_token_indices, issues).
    """
    consumed: set[int] = set()
    line_items: list[LineItem] = []
    issues: list[Issue] = []
    catalogue_by_id = {sku.sku_id: sku for sku in catalogue}
    display_tokens = raw_tokens if raw_tokens is not None else tokens

    num_tokens = len(tokens)

    # 1. Group around recognized ITEM spans
    for span in item_spans:
        if span.label != "ITEM":
            continue

        cluster_start = span.start
        cluster_end = span.end

        # Expand backward to absorb adjacent QTY / UNIT / MONEY
        has_backward_qty = False
        while cluster_start > 0:
            prev_label = labels[cluster_start - 1]
            if prev_label in ("QTY", "UNIT", "MONEY") and (cluster_start - 1) not in consumed:
                cluster_start -= 1
                if prev_label == "QTY":
                    has_backward_qty = True
            else:
                break

        # Expand forward ONLY if we did not already absorb a QTY backward
        # Commercial Urdu uses pre-modifier quantifiers (do kilo cheeni);
        # do not steal the following item's prefix quantifier.
        if not has_backward_qty:
            while cluster_end < num_tokens:
                next_label = labels[cluster_end]
                if next_label in ("QTY", "UNIT", "MONEY") and cluster_end not in consumed:
                    cluster_end += 1
                else:
                    break

        cluster_indices = list(range(cluster_start, cluster_end))
        for idx in cluster_indices:
            consumed.add(idx)

        # Parse QTY
        parsed_qty, unit_hint = _parse_cluster_qty(tokens, cluster_indices)
        qty = parsed_qty if parsed_qty is not None else 1.0

        # Parse UNIT & Unit multiplier (e.g. paw = 0.25 kg)
        unit: Unit | None = None
        has_paw = False
        unit_multiplier = 1.0
        for idx in cluster_indices:
            if labels[idx] == "UNIT" or tokens[idx] == _PAW_FOLDED:
                if tokens[idx] == _PAW_FOLDED:
                    has_paw = True
                u = resolve_unit(tokens[idx])
                if u is not None:
                    unit = cast(Unit, u[0])
                    unit_multiplier = u[1]
                    break

        sku = catalogue_by_id.get(span.ref_id or "")
        sku_default_unit = sku.default_unit if sku else None

        # Paw disambiguation & validation (docs/01 §5 & §8 Case 7)
        if has_paw:
            if sku is not None and sku_default_unit not in ("kg", "g"):
                # Non-mass unit with paw is ambiguous -> blocking
                issues.append(
                    Issue(
                        rule="V4",
                        item_index=len(line_items),
                        message=f"Ambiguous 'paw' used with non-mass SKU '{sku.display_name}'",
                    )
                )
                span.match_status = "ambiguous"
            else:
                if unit is None:
                    unit = "kg"
                # If paw was used as unit and qty was parsed from preceding cardinal (e.g. aik paw)
                # apply the unit multiplier (0.25)
                if unit_multiplier != 1.0:
                    qty *= unit_multiplier

        if unit is None and unit_hint is not None:
            unit = cast(Unit, unit_hint)
        if unit is None and sku_default_unit is not None:
            unit = sku_default_unit

        item = LineItem(
            sku_id=span.ref_id,
            raw_name=span.raw_name,
            display_name=span.display_name or (sku.display_name if sku else None),
            qty=qty,
            unit=unit,
            spoken_amount=None,
            unit_price=sku.unit_price if sku else None,
            line_total=None,
            price_source="catalogue" if (sku and sku.unit_price) else "missing",
            match_score=span.score / 100.0,
            match_status=span.match_status,  # type: ignore[arg-type]
            candidates=span.candidates,
            derived_fields=[],
            token_span=(cluster_start, cluster_end),
        )
        line_items.append(item)

    # 2. Check for provisional items: unlabelled word adjacent to QTY or UNIT
    # Case 9: Unknown word adjacent to a qty -> provisional SKU
    for idx in range(num_tokens):
        if idx in consumed:
            continue
        if labels[idx] is not None:
            continue

        # Check if adjacent to an unconsumed QTY or UNIT token
        adjacent_qty_or_unit = False
        adj_indices: list[int] = []

        if idx > 0 and (idx - 1) not in consumed and labels[idx - 1] in ("QTY", "UNIT"):
            adjacent_qty_or_unit = True
            adj_indices.append(idx - 1)
            curr = idx - 1
            while curr > 0 and (curr - 1) not in consumed and labels[curr - 1] in ("QTY", "UNIT"):
                adj_indices.append(curr - 1)
                curr -= 1

        if idx + 1 < num_tokens and (idx + 1) not in consumed and labels[idx + 1] in ("QTY", "UNIT"):
            adjacent_qty_or_unit = True
            adj_indices.append(idx + 1)
            curr = idx + 1
            while curr + 1 < num_tokens and (curr + 1) not in consumed and labels[curr + 1] in ("QTY", "UNIT"):
                adj_indices.append(curr + 1)
                curr += 1

        if adjacent_qty_or_unit:
            full_cluster = sorted([idx] + adj_indices)
            for c_idx in full_cluster:
                consumed.add(c_idx)

            parsed_qty, unit_hint = _parse_cluster_qty(tokens, full_cluster)
            qty = parsed_qty if parsed_qty is not None else 1.0

            prov_unit: Unit | None = None
            for c_idx in full_cluster:
                if labels[c_idx] == "UNIT":
                    u = resolve_unit(tokens[c_idx])
                    if u is not None:
                        prov_unit = cast(Unit, u[0])
                        break
            if prov_unit is None and unit_hint is not None:
                prov_unit = cast(Unit, unit_hint)

            prov_item = LineItem(
                sku_id=None,
                raw_name=display_tokens[idx],
                display_name=None,
                qty=qty,
                unit=prov_unit,
                spoken_amount=None,
                unit_price=None,
                line_total=None,
                price_source="missing",
                match_score=0.3,  # per docs/02 §5
                match_status="provisional",
                candidates=[],
                derived_fields=[],
                token_span=(min(full_cluster), max(full_cluster) + 1),
            )
            line_items.append(prov_item)

    return line_items, consumed, issues
