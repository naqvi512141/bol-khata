"""Per-request telemetry — one JSON line per request.

Appends to server/logs/ as JSON lines.

Each line contains:
- job_id, shop_id, draft_id
- per-stage timings (ingest_ms, asr_ms, normalize_ms, extract_ms, pricing_ms,
  validation_ms, llm_ms, total_ms)
- asr_engine, failover_reason
- path (fast | llm | manual)
- order_form
- price_source distribution (spoken_count, catalogue_count, missing_count)
- confidence
- item_count
- timestamp
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Telemetry for a single /v1/utterance request."""

    job_id: str = ""
    shop_id: str = ""
    draft_id: str = ""

    # Per-stage timings (milliseconds)
    ingest_ms: int = 0
    asr_ms: int = 0
    normalize_ms: int = 0
    extract_ms: int = 0
    pricing_ms: int = 0
    validation_ms: int = 0
    llm_ms: int = 0
    total_ms: int = 0

    # ASR engine info — surfaced in response and telemetry
    asr_engine: str = ""
    failover_reason: str | None = None

    # Pipeline outcome
    path: str = ""  # fast | llm | manual
    order_form: str = ""
    confidence: float = 0.0

    # Price source distribution
    spoken_count: int = 0
    catalogue_count: int = 0
    missing_count: int = 0

    # Item count
    item_count: int = 0

    # Timestamp
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def log_metrics(metrics: RequestMetrics, log_dir: str = "./logs") -> None:
    """Append one JSON line to the telemetry log file.

    Creates the log directory and file if they don't exist.
    File: {log_dir}/telemetry.jsonl
    """
    try:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = log_path / "telemetry.jsonl"

        line = json.dumps(asdict(metrics), ensure_ascii=False, default=str)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # Telemetry must never crash the request
        logger.exception("Failed to write telemetry line for job_id=%s", metrics.job_id)
