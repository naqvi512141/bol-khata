"""Fixtures for extractor tests."""

import json
from pathlib import Path

import pytest

from app.schemas import Customer, SKU

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture
def catalogue() -> list[SKU]:
    """Load the 40 demo SKUs from server/data/catalogue.json."""
    path = DATA_DIR / "catalogue.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [SKU(**item) for item in raw]


@pytest.fixture
def customers() -> list[Customer]:
    """Load the 15 demo customers from server/data/customers.json."""
    path = DATA_DIR / "customers.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Customer(**item) for item in raw]
