"""Tests for server/app/telemetry/metrics.py.

Contract:
- Telemetry: one JSON line per request with per-stage timings, path,
  order_form, price_source distribution and confidence.
- Surface asr_engine and failover_reason in every telemetry line.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.telemetry.metrics import RequestMetrics, log_metrics


def test_request_metrics_defaults() -> None:
    metrics = RequestMetrics(job_id="j_01", shop_id="s_01")
    assert metrics.job_id == "j_01"
    assert metrics.ingest_ms == 0
    assert metrics.asr_engine == ""
    assert metrics.failover_reason is None
    assert metrics.spoken_count == 0
    assert metrics.catalogue_count == 0
    assert metrics.missing_count == 0


def test_log_metrics_writes_parseable_jsonl(tmp_path: Path) -> None:
    log_dir = str(tmp_path / "logs")
    metrics1 = RequestMetrics(
        job_id="j_001",
        shop_id="demo_shop_01",
        draft_id="d_001",
        ingest_ms=12,
        asr_ms=650,
        normalize_ms=1,
        extract_ms=5,
        pricing_ms=2,
        validation_ms=1,
        llm_ms=0,
        total_ms=671,
        asr_engine="groq_whisper",
        failover_reason=None,
        path="fast",
        order_form="canonical",
        confidence=0.95,
        spoken_count=0,
        catalogue_count=2,
        missing_count=0,
        item_count=2,
    )
    metrics2 = RequestMetrics(
        job_id="j_002",
        shop_id="demo_shop_01",
        draft_id="d_002",
        ingest_ms=15,
        asr_ms=12000,
        asr_engine="local_faster_whisper",
        failover_reason="auth_failure",
        path="manual",
        order_form="no_name_cash",
        confidence=0.82,
        spoken_count=1,
        catalogue_count=0,
        missing_count=0,
        item_count=1,
    )

    log_metrics(metrics1, log_dir=log_dir)
    log_metrics(metrics2, log_dir=log_dir)

    log_file = Path(log_dir) / "telemetry.jsonl"
    assert log_file.exists()

    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2

    row1 = json.loads(lines[0])
    assert row1["job_id"] == "j_001"
    assert row1["asr_engine"] == "groq_whisper"
    assert row1["failover_reason"] is None
    assert row1["path"] == "fast"
    assert row1["order_form"] == "canonical"
    assert row1["confidence"] == 0.95
    assert row1["catalogue_count"] == 2

    row2 = json.loads(lines[1])
    assert row2["job_id"] == "j_002"
    assert row2["asr_engine"] == "local_faster_whisper"
    assert row2["failover_reason"] == "auth_failure"
    assert row2["path"] == "manual"
