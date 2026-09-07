"""Catalogue management and price history tracking.

Docs: docs/02-contracts.md §6, §7; docs/03-build-plan.md Phase 4.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from app.schemas import SKU, PricePoint


class Catalogue:
    """Manages SKUs, current prices, price observations, and historical medians."""

    def __init__(self, skus: Sequence[SKU] | None = None) -> None:
        self.skus: dict[str, SKU] = {sku.sku_id: sku for sku in (skus or [])}

    @classmethod
    def from_json(cls, source: Path | str) -> Catalogue:
        """Load catalogue from a file path or JSON string."""
        if isinstance(source, Path) or (
            isinstance(source, str)
            and not source.strip().startswith("[")
            and not source.strip().startswith("{")
        ):
            path = Path(source)
            text = path.read_text(encoding="utf-8")
        else:
            text = str(source)

        data = json.loads(text)
        if isinstance(data, list):
            skus = [SKU(**item) for item in data]
        elif isinstance(data, dict) and "skus" in data:
            skus = [SKU(**item) for item in data["skus"]]
        else:
            raise ValueError("Invalid catalogue JSON format")
        return cls(skus)

    def get_sku(self, sku_id: str | None) -> SKU | None:
        """Return SKU by ID or None."""
        if not sku_id:
            return None
        return self.skus.get(sku_id)

    def current_price(self, sku_id: str | None) -> int | None:
        """Return the current unit price in integer PKR for the given SKU, or None."""
        sku = self.get_sku(sku_id)
        if sku is None or sku.unit_price is None:
            return None
        return sku.unit_price

    def observe_price(
        self,
        sku_id: str | None,
        amount: int,
        qty: float | None = None,
        observed_at: str | None = None,
    ) -> None:
        """Record an observed price into the SKU's price history.

        amount: Total PKR observed for the line.
        qty: Spoken quantity (defaults to 1.0 if not given or <= 0).
        PricePoint stores the unit price in integer PKR: round once and store.
        """
        if not sku_id:
            return
        sku = self.get_sku(sku_id)
        if sku is None:
            return

        effective_qty = float(qty) if (qty is not None and qty > 0) else 1.0
        # No float in money: round once at computation and store as int PKR -- AGENTS.md rule 1
        unit_price = round(amount / effective_qty)
        ts = observed_at or datetime.now(UTC).isoformat()
        sku.price_history.append(
            PricePoint(price=unit_price, qty=effective_qty, observed_at=ts)
        )

    def median_price(self, sku_id: str | None) -> int | None:
        """Return the median unit price from the last 10 entries in integer PKR.

        Returns None if fewer than 3 entries exist (no reliable baseline).
        Per docs/02 §7 & docs/03 Phase 4.
        """
        sku = self.get_sku(sku_id)
        if sku is None or len(sku.price_history) < 3:
            return None

        # Take last 10 observations
        window = sku.price_history[-10:]
        prices = [p.price for p in window]
        med = statistics.median(prices)
        # Integer PKR -- AGENTS.md rule 1
        return round(med)
