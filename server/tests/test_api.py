"""Phase 6 API and end-to-end pipeline tests.

Docs: docs/03-build-plan.md Phase 6; docs/02-contracts.md §8.

Rules:
- Idempotent on job_id. A repeated job_id returns the cached ParsedDraft and
  must never reprocess.
- The LLM is invoked ONLY when validation.requires_llm is True.
- LLM output is re-run through the FULL validation gate. It never bypasses it.
- LLM_PROVIDER=none must be a valid configuration. The app runs with no LLM.
- Telemetry: one JSON line per request with per-stage timings, path,
  order_form, price_source distribution and confidence.
- End-to-end test with real ASR output (sample_ur.wav).
- Surface asr_engine and failover_reason in the response and telemetry line.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import wave

import numpy as np
import pytest
from starlette.testclient import TestClient

try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:
    pass

from app.asr.groq_whisper import GroqASRError
from app.config import Settings
from app.ingest.audio import IngestedAudio
from app.main import app, _job_cache
from app.schemas import (
    CustomerRef,
    Issue,
    LineItem,
    ParsedDraft,
    RawASRPayload,
    ValidationResult,
)


_FIXTURE_WAV = Path(__file__).resolve().parent / "fixtures" / "sample_ur.wav"


@pytest.fixture(autouse=True)
def clear_job_cache() -> None:
    """Clear idempotency job cache between tests."""
    _job_cache.clear()


def _make_dummy_wav(duration_s: float = 1.0) -> bytes:
    """Create a dummy WAV file in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # 16000 samples per second
        samples = (np.sin(np.linspace(0, 440 * 2 * np.pi * duration_s, int(16000 * duration_s))) * 10000).astype(np.int16)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


def _make_dummy_asr_payload(
    raw_text: str = "احمد دو کلو چینی",
    job_id: str = "job_test",
    shop_id: str = "demo_shop_01",
    engine: str = "groq_whisper",
    failover_reason: str | None = None,
    asr_confidence: float = 0.95,
) -> RawASRPayload:
    return RawASRPayload(
        job_id=job_id,
        shop_id=shop_id,
        audio_ref=f"audio_{job_id}.wav",
        engine=engine,  # type: ignore[arg-type]
        failover_reason=failover_reason,
        model_name="whisper-large-v3",
        language="ur",
        raw_text=raw_text,
        segments=[],
        duration_ms=1000,
        asr_confidence=asr_confidence,
    )


# ==================== Health, Catalogue, Customer endpoints ====================


def test_health_endpoint() -> None:
    client = TestClient(app)
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "asr_engine" in data
    assert data["version"] == "0.1.0"


def test_catalogue_endpoint() -> None:
    client = TestClient(app)
    resp = client.get("/v1/catalogue/demo_shop_01")
    assert resp.status_code == 200
    skus = resp.json()
    assert len(skus) >= 40
    sku_ids = {s["sku_id"] for s in skus}
    assert "SKU_001" in sku_ids  # cheeni


def test_customers_endpoint() -> None:
    client = TestClient(app)
    resp = client.get("/v1/customers/demo_shop_01")
    assert resp.status_code == 200
    custs = resp.json()
    assert len(custs) >= 15
    cust_ids = {c["customer_id"] for c in custs}
    assert "CUST_001" in cust_ids  # ahmed


# ==================== Audio validation on /v1/utterance ====================


def test_utterance_audio_too_short() -> None:
    """Audio shorter than 700 ms is rejected with HTTP 400 audio_too_short."""
    client = TestClient(app)
    short_wav = _make_dummy_wav(0.5)  # 500 ms
    resp = client.post(
        "/v1/utterance",
        files={"audio": ("audio.wav", short_wav, "audio/wav")},
        data={"shop_id": "demo_shop_01", "job_id": "job_short_01"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["code"] == "audio_too_short"


# ==================== Idempotency on job_id ====================


def test_utterance_idempotency_returns_cached_draft() -> None:
    """Repeated job_id returns HTTP 200 with cached result, idempotent_replay=True, and does not reprocess."""
    client = TestClient(app)
    audio_wav = _make_dummy_wav(1.0)

    # Mock ASR service to verify call count
    mock_payload = _make_dummy_asr_payload(job_id="job_idem_01")

    with patch("app.main._get_asr_service") as mock_get_asr:
        mock_service = MagicMock()
        mock_service.transcribe.return_value = mock_payload
        mock_get_asr.return_value = mock_service

        # First request
        resp1 = client.post(
            "/v1/utterance",
            files={"audio": ("audio.wav", audio_wav, "audio/wav")},
            data={"shop_id": "demo_shop_01", "job_id": "job_idem_01"},
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["idempotent_replay"] is False

        # Second request with SAME job_id
        resp2 = client.post(
            "/v1/utterance",
            files={"audio": ("audio.wav", audio_wav, "audio/wav")},
            data={"shop_id": "demo_shop_01", "job_id": "job_idem_01"},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["idempotent_replay"] is True

        # Assert body is byte-identical to first response except idempotent_replay
        modified_bytes = resp2.content.replace(
            b'"idempotent_replay":true', b'"idempotent_replay":false'
        )
        assert modified_bytes == resp1.content

        # Also assert parsed dictionaries match with idempotent_replay updated
        expected_data2 = dict(data1)
        expected_data2["idempotent_replay"] = True
        assert data2 == expected_data2

        # ASR was called exactly once — not reprocessed!
        assert mock_service.transcribe.call_count == 1


# ==================== LLM invocation gating ====================


def _make_dummy_draft(
    stated_total: int | None = None,
    customer_status: str = "resolved",
    payment_type: str = "udhaar",
    customer_id: str | None = "CUST_001",
) -> ParsedDraft:
    return ParsedDraft(
        draft_id="d_test",
        job_ids=["job_test"],
        shop_id="demo_shop_01",
        customer=CustomerRef(
            customer_id=customer_id,
            raw_name="احمد",
            status=customer_status,  # type: ignore[arg-type]
            confidence=0.95 if customer_status == "resolved" else 0.5,
            candidates=[customer_id] if customer_id else [],
            source="spoken",
        ),
        items=[
            LineItem(
                sku_id="SKU_001",
                raw_name="چینی",
                display_name="Cheeni (Sugar)",
                qty=2.0,
                unit="kg",
                unit_price=180,
                line_total=360,
                price_source="catalogue",
                match_score=100.0,
                match_status="resolved",
                candidates=["SKU_001"],
                derived_fields=["line_total"],
                token_span=(0, 2),
            )
        ],
        residue=[],
        stated_total=stated_total,
        computed_total=360,
        payment_type=payment_type,  # type: ignore[arg-type]
        currency="PKR",
        order_form="canonical",
        confidence=0.9,
        path="fast",
        validation=ValidationResult(passed=True),
        normalized_tokens="احمد دو کلو چینی",
        raw_texts=["احمد دو کلو چینی"],
    )


# ==================== LLM invocation gating ====================


def test_llm_not_invoked_when_only_v6_blocking() -> None:
    """The LLM is NOT called when the only blocking issue is V6 (customer identity) or V7.

    Per docs/03 Phase 6 & validation rules: V6/V7 need a human, not a model.
    """
    client = TestClient(app)
    audio_wav = _make_dummy_wav(1.0)
    mock_payload = _make_dummy_asr_payload(job_id="job_v6_no_llm")

    # Draft has ambiguous customer on credit (triggers V6 blocking)
    ambiguous_draft = _make_dummy_draft(
        customer_status="ambiguous",
        payment_type="udhaar",
        customer_id=None,
    )

    with (
        patch("app.main._get_asr_service") as mock_get_asr,
        patch("app.main.extract", return_value=ambiguous_draft),
        patch("app.main.llm_repair") as mock_repair,
    ):
        mock_service = MagicMock()
        mock_service.transcribe.return_value = mock_payload
        mock_get_asr.return_value = mock_service

        resp = client.post(
            "/v1/utterance",
            files={"audio": ("audio.wav", audio_wav, "audio/wav")},
            data={"shop_id": "demo_shop_01", "job_id": "job_v6_no_llm"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["validation"]["passed"] is False
        assert any(i["rule"] == "V6" for i in data["validation"]["blocking"])
        assert data["validation"]["requires_llm"] is False
        assert data["path"] == "manual"
        # LLM must NOT be called!
        mock_repair.assert_not_called()


def test_llm_invoked_when_requires_llm_true_and_reruns_validation() -> None:
    """When validation.requires_llm is True, LLM is called and output re-runs through validation."""
    client = TestClient(app)
    audio_wav = _make_dummy_wav(1.0)
    mock_payload = _make_dummy_asr_payload(job_id="job_llm_repair_01")

    # Draft with stated total mismatch: stated 500, but items total 360 -> V1 failure
    mismatch_draft = _make_dummy_draft(stated_total=500)

    with (
        patch("app.main._get_asr_service") as mock_get_asr,
        patch("app.main.extract", return_value=mismatch_draft),
        patch("app.main.get_llm_provider") as mock_get_provider,
        patch("app.main.llm_repair") as mock_repair,
    ):
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider
        mock_service = MagicMock()
        mock_service.transcribe.return_value = mock_payload
        mock_get_asr.return_value = mock_service

        # Mock LLM repair to fix the stated total / items
        def fake_repair(draft, provider):
            fixed_item = draft.items[0].model_copy()
            fixed_item.line_total = 500
            fixed_item.unit_price = 250
            return [fixed_item], 500, True

        mock_repair.side_effect = fake_repair

        resp = client.post(
            "/v1/utterance",
            files={"audio": ("audio.wav", audio_wav, "audio/wav")},
            data={"shop_id": "demo_shop_01", "job_id": "job_llm_repair_01"},
        )

        assert resp.status_code == 200
        data = resp.json()
        # Verify LLM was invoked
        mock_repair.assert_called_once()
        # Verify LLM output was re-validated and path set to "llm"
        assert data["path"] == "llm"
        assert data["computed_total"] == 500


def test_llm_provider_none_configuration() -> None:
    """When LLM_PROVIDER=none, app runs with no LLM and sets path='manual' without error."""
    client = TestClient(app)
    audio_wav = _make_dummy_wav(1.0)
    mock_payload = _make_dummy_asr_payload(job_id="job_no_llm_cfg")
    mismatch_draft = _make_dummy_draft(stated_total=500)

    with (
        patch("app.main._get_asr_service") as mock_get_asr,
        patch("app.main.extract", return_value=mismatch_draft),
        patch("app.main._get_settings") as mock_settings,
        patch("app.main.llm_repair") as mock_repair,
    ):
        mock_service = MagicMock()
        mock_service.transcribe.return_value = mock_payload
        mock_get_asr.return_value = mock_service

        # Configure LLM_PROVIDER=none
        mock_settings.return_value = Settings(LLM_PROVIDER="none", LOG_DIR="./logs")

        resp = client.post(
            "/v1/utterance",
            files={"audio": ("audio.wav", audio_wav, "audio/wav")},
            data={"shop_id": "demo_shop_01", "job_id": "job_no_llm_cfg"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == "manual"
        # LLM repair was never called
        mock_repair.assert_not_called()


# ==================== Telemetry and Engine Visibility ====================


def test_telemetry_and_engine_visibility(tmp_path: Path) -> None:
    """Surface asr_engine and failover_reason in the response and telemetry line."""
    client = TestClient(app)
    audio_wav = _make_dummy_wav(1.0)

    mock_payload = _make_dummy_asr_payload(
        raw_text="احمد بھائی دو کلو چینی",
        job_id="job_telemetry_test",
        engine="local_faster_whisper",
        failover_reason="auth_failure",
        asr_confidence=0.88,
    )

    log_dir = str(tmp_path / "test_logs")

    with (
        patch("app.main._get_asr_service") as mock_get_asr,
        patch("app.main._get_settings") as mock_settings,
    ):
        mock_service = MagicMock()
        mock_service.transcribe.return_value = mock_payload
        mock_get_asr.return_value = mock_service
        mock_settings.return_value = Settings(LOG_DIR=log_dir)

        resp = client.post(
            "/v1/utterance",
            files={"audio": ("audio.wav", audio_wav, "audio/wav")},
            data={"shop_id": "demo_shop_01", "job_id": "job_telemetry_test"},
        )

        assert resp.status_code == 200
        data = resp.json()

        # Engine visibility in response
        assert data["asr_engine"] == "local_faster_whisper"
        assert data["failover_reason"] == "auth_failure"

        # Verify telemetry log
        log_file = Path(log_dir) / "telemetry.jsonl"
        assert log_file.exists()
        telemetry = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert telemetry["job_id"] == "job_telemetry_test"
        assert telemetry["asr_engine"] == "local_faster_whisper"
        assert telemetry["failover_reason"] == "auth_failure"
        assert "ingest_ms" in telemetry
        assert "asr_ms" in telemetry
        assert "normalize_ms" in telemetry
        assert "extract_ms" in telemetry
        assert "pricing_ms" in telemetry
        assert "validation_ms" in telemetry
        assert "total_ms" in telemetry
        assert telemetry["path"] == "fast"
        assert telemetry["order_form"] == "canonical"


# ==================== End-to-End Live ASR Integration Test ====================


@pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"),
    reason="End-to-end live ASR test requires GROQ_API_KEY in environment",
)
@pytest.mark.skipif(
    not _FIXTURE_WAV.exists(),
    reason=f"Real audio fixture not found at {_FIXTURE_WAV}",
)
def test_end_to_end_real_asr_sample_ur() -> None:
    """POST server/tests/fixtures/sample_ur.wav to /v1/utterance and assert full response.

    Customer resolves to Ahmed, exactly two line items (2 kg cheeni and 0.5 kg besan),
    order_form 'canonical', path 'fast' (no LLM needed), asr_engine 'groq_whisper'.
    """
    client = TestClient(app)
    wav_bytes = _FIXTURE_WAV.read_bytes()

    resp = client.post(
        "/v1/utterance",
        files={"audio": ("sample_ur.wav", wav_bytes, "audio/wav")},
        data={"shop_id": "demo_shop_01", "job_id": "live_e2e_sample_ur_01"},
    )

    assert resp.status_code == 200
    data = resp.json()

    # Customer resolves to Ahmed
    assert data["customer"]["status"] == "resolved"
    assert data["customer"]["customer_id"] == "CUST_001"
    assert "احمد" in (data["customer"]["raw_name"] or "")

    # Exactly two line items: 2 kg cheeni and 0.5 kg besan
    assert len(data["items"]) == 2

    # Item 1: 2 kg cheeni
    item1 = data["items"][0]
    assert item1["sku_id"] == "SKU_001"
    assert item1["qty"] == 2.0
    assert item1["unit"] == "kg"
    assert item1["line_total"] == 360  # 2 kg * 180 PKR/kg

    # Item 2: 0.5 kg besan
    item2 = data["items"][1]
    assert item2["sku_id"] == "SKU_006"
    assert item2["qty"] == 0.5
    assert item2["unit"] == "kg"
    assert item2["line_total"] == 140  # 0.5 kg * 280 PKR/kg

    # Computed total (360 + 140 = 500 integer PKR — AGENTS.md rule 1)
    assert data["computed_total"] == 500

    # Order form "canonical"
    assert data["order_form"] == "canonical"

    # Path "fast" (no LLM needed)
    assert data["path"] == "fast"

    # Validation passed
    assert data["validation"]["passed"] is True
    assert data["validation"]["blocking"] == []

    # ASR engine and failover visible
    assert data["asr_engine"] == "groq_whisper"
    assert data["failover_reason"] is None
