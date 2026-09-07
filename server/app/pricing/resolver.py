"""Three-tier price resolver.

Price priority is strictly:
  1. Spoken price (from line.spoken_amount)
  2. Catalogue lookup (from catalogue.current_price)
  3. Missing (line.price_source = 'missing')

Docs: docs/02-contracts.md §6.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.pricing.catalogue import Catalogue
from app.schemas import LineItem


def resolve_price(line: LineItem, catalogue: Catalogue) -> LineItem:
    """Resolve price for a single line item according to three-tier priority."""
    # Priority 1: spoken amount
    if line.spoken_amount is not None:
        line.line_total = line.spoken_amount  # int PKR -- AGENTS.md rule 1
        line.price_source = "spoken"
        catalogue.observe_price(line.sku_id, line.spoken_amount, line.qty)
        return line

    # Priority 2: catalogue lookup
    unit_price = catalogue.current_price(line.sku_id)
    if unit_price is not None:
        line.unit_price = unit_price
        effective_qty = line.qty if line.qty is not None else 1.0
        # Round once at computation and store as int PKR -- AGENTS.md rule 1
        line.line_total = round(unit_price * effective_qty)
        line.price_source = "catalogue"
        if "line_total" not in line.derived_fields:
            line.derived_fields.append("line_total")
        return line

    # Priority 3: missing -> rule V7, blocking
    line.price_source = "missing"
    line.line_total = None
    return line


def resolve_prices(items: Sequence[LineItem], catalogue: Catalogue) -> list[LineItem]:
    """Resolve prices for all line items in a draft."""
    return [resolve_price(item, catalogue) for item in items]
