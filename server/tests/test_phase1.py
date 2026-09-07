"""Phase 1 smoke tests — schemas import and health endpoint."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import (
    ASRSegment,
    Customer,
    CustomerRef,
    Issue,
    LineItem,
    OrderForm,
    ParsedDraft,
    PricePoint,
    RawASRPayload,
    ResidueSpan,
    SKU,
    Unit,
    ValidationResult,
)


client = TestClient(app)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_health_endpoint() -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_schemas_import() -> None:
    """Verify all schema classes are importable and constructable."""
    seg = ASRSegment(text="test", start=0.0, end=1.0, avg_logprob=-0.5, no_speech_prob=0.1)
    assert seg.text == "test"

    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        match_status="resolved",
        token_span=(0, 1),
    )
    assert item.price_source == "missing"
    assert item.spoken_amount is None  # money field defaults to None, not float

    cust = CustomerRef(status="absent", source="cash_default")
    assert cust.customer_id is None

    val = ValidationResult(passed=True)
    assert val.blocking == []

    draft = ParsedDraft(
        draft_id="d001",
        job_ids=["j001"],
        shop_id="demo_shop_01",
        customer=cust,
        items=[item],
        computed_total=360,
        payment_type="cash",
        order_form="no_name_cash",
        confidence=0.5,
        path="fast",
        validation=val,
        normalized_tokens="دو کلو چینی",
    )
    assert draft.stated_total is None
    assert isinstance(draft.computed_total, int)  # money is int -- AGENTS.md rule 1


def test_money_fields_are_int() -> None:
    """AGENTS.md rule 1: money is int, always, everywhere."""
    item = LineItem(
        sku_id="SKU_001",
        raw_name="چینی",
        spoken_amount=360,
        unit_price=180,
        line_total=360,
        match_status="resolved",
        token_span=(0, 1),
    )
    assert isinstance(item.spoken_amount, int)
    assert isinstance(item.unit_price, int)
    assert isinstance(item.line_total, int)

    sku = SKU(sku_id="SKU_001", display_name="چینی", default_unit="kg", unit_price=180)
    assert isinstance(sku.unit_price, int)

    pp = PricePoint(price=180, qty=1.0, observed_at="2026-09-07T00:00:00+05:00")
    assert isinstance(pp.price, int)

    cust = Customer(customer_id="CUST_001", display_name="احمد", balance=2500)
    assert isinstance(cust.balance, int)


def test_catalogue_json_valid() -> None:
    """catalogue.json loads and every SKU validates against the schema."""
    path = DATA_DIR / "catalogue.json"
    assert path.exists(), f"Missing {path}"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert len(raw) == 40
    skus = [SKU(**entry) for entry in raw]
    # Check the five multi-token SKU names from docs/01 §9
    display_names = {s.display_name for s in skus}
    all_aliases = set()
    for s in skus:
        all_aliases.update(a.lower() for a in s.aliases)
    for multi_token in ["laal mirch", "chai patti", "desi ghee", "surf excel", "haldi powder"]:
        assert multi_token in all_aliases, f"Multi-token SKU '{multi_token}' not found in aliases"
    # unit_price is int or None
    for s in skus:
        if s.unit_price is not None:
            assert isinstance(s.unit_price, int), f"{s.sku_id} unit_price is not int"


def test_customers_json_valid() -> None:
    """customers.json loads and has the near-duplicate names."""
    path = DATA_DIR / "customers.json"
    assert path.exists(), f"Missing {path}"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert len(raw) == 15
    customers = [Customer(**entry) for entry in raw]
    # Near-duplicates: two variants of Ahmed, one Ahmad
    all_aliases = []
    for c in customers:
        all_aliases.extend(a.lower() for a in c.aliases)
    ahmed_count = sum(1 for a in all_aliases if "ahmed" in a or "ahmad" in a)
    assert ahmed_count >= 3, "Need at least 3 Ahmed/Ahmad aliases for margin check exercise"
    # balance is int
    for c in customers:
        assert isinstance(c.balance, int), f"{c.customer_id} balance is not int"


def test_urdu_numerals_json_valid() -> None:
    """urdu_numerals.json loads with cardinals, gaps marked, and quantifiers."""
    path = DATA_DIR / "urdu_numerals.json"
    assert path.exists(), f"Missing {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    cardinals = data["cardinals"]
    # Check that 0-30 are present
    values = set(cardinals.values())
    for n in range(31):
        assert n in values, f"Cardinal {n} missing from table"
    # Gaps are documented
    assert "cardinal_gaps" in data
    assert len(data["cardinal_gaps"]) > 0
    # Multipliers
    assert data["multipliers"]["سو"] == 100
    assert data["multipliers"]["ہزار"] == 1000
    assert data["multipliers"]["لاکھ"] == 100000
    # paun subtracts -- AGENTS.md rule 3
    assert data["modifier_quantifiers"]["پونے"] == -0.25


def test_corpus_manifest_valid() -> None:
    """corpus/manifest.json has the expected structure."""
    path = DATA_DIR / "corpus" / "manifest.json"
    assert path.exists(), f"Missing {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "utterances" in data
    assert len(data["utterances"]) > 0
    for u in data["utterances"]:
        assert "id" in u
        assert "ground_truth_text" in u
        assert "expected" in u
        assert "tags" in u
