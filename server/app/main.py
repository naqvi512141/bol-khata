"""FastAPI app — routes only.

Phase 6: POST /v1/utterance wiring the full pipeline,
GET /v1/catalogue/{shop_id}, GET /v1/customers/{shop_id}.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.asr.service import ASRService
from app.config import Settings, get_settings
from app.extractor import extract
from app.ingest.audio import process_audio
from app.ingest.exceptions import AudioIngestError, AudioTooLongError, AudioTooShortError, BadCodecError
from app.llm.providers import NoLLMProvider, get_llm_provider
from app.llm.repair import llm_repair
from app.normalizer import normalize
from app.pricing.catalogue import Catalogue
from app.pricing.resolver import resolve_prices
from app.schemas import (
    SKU,
    Customer,
    ParsedDraft,
    UtteranceResponse,
)
from app.telemetry.metrics import RequestMetrics, log_metrics
from app.validation.confidence import compute_asr_confidence, compute_confidence
from app.validation.rules import validate

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bol Khata",
    description="Voice-first credit ledger for Pakistani kiryana shopkeepers",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# Singletons — initialized at startup
# ---------------------------------------------------------------------------
_settings: Settings | None = None
_asr_service: ASRService | None = None
_catalogue: Catalogue | None = None
_customers: list[Customer] = []
_skus: list[SKU] = []
_job_cache: dict[str, UtteranceResponse] = {}  # idempotency cache, in-memory for demo


def _get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = get_settings()
    return _settings


def _get_asr_service() -> ASRService:
    global _asr_service
    if _asr_service is None:
        _asr_service = ASRService(settings=_get_settings())
    return _asr_service


def _get_catalogue() -> Catalogue:
    global _catalogue
    if _catalogue is None:
        data_dir = Path(__file__).parent.parent / "data"
        catalogue_path = data_dir / "catalogue.json"
        _catalogue = Catalogue.from_json(catalogue_path)
    return _catalogue


def _get_customers() -> list[Customer]:
    global _customers
    if not _customers:
        data_dir = Path(__file__).parent.parent / "data"
        customers_path = data_dir / "customers.json"
        raw = json.loads(customers_path.read_text(encoding="utf-8"))
        _customers = [Customer(**c) for c in raw]
    return _customers


def _get_skus() -> list[SKU]:
    global _skus
    if not _skus:
        cat = _get_catalogue()
        _skus = list(cat.skus.values())
    return _skus


# ---------------------------------------------------------------------------
# GET /v1/health
# ---------------------------------------------------------------------------
@app.get("/v1/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    settings = _get_settings()
    return {
        "status": "ok",
        "asr_engine": settings.ASR_ENGINE,
        "version": "0.1.0",
    }


# ---------------------------------------------------------------------------
# GET /v1/catalogue/{shop_id}
# ---------------------------------------------------------------------------
@app.get("/v1/catalogue/{shop_id}")
async def get_catalogue(shop_id: str) -> list[dict[str, Any]]:
    """Return the catalogue SKUs for a given shop."""
    skus = _get_skus()
    return [s.model_dump(mode="json") for s in skus]


# ---------------------------------------------------------------------------
# GET /v1/customers/{shop_id}
# ---------------------------------------------------------------------------
@app.get("/v1/customers/{shop_id}")
async def get_customers(shop_id: str) -> list[dict[str, Any]]:
    """Return the customer list for a given shop."""
    customers = _get_customers()
    return [c.model_dump(mode="json") for c in customers]


# ---------------------------------------------------------------------------
# POST /v1/utterance — the full pipeline
# ---------------------------------------------------------------------------
@app.post("/v1/utterance")
async def post_utterance(
    audio: Annotated[UploadFile, File()],
    shop_id: Annotated[str, Form()],
    job_id: Annotated[str, Form()],
    draft_id: Annotated[str | None, Form()] = None,
    captured_at: Annotated[str | None, Form()] = None,
    client_meta: Annotated[str | None, Form()] = None,
) -> JSONResponse:
    """Process an audio utterance through the full pipeline.

    Idempotent on job_id: a repeated job_id returns the cached ParsedDraft
    and must never reprocess (docs/02 §8).
    """
    # -----------------------------------------------------------------------
    # Idempotency check — return cached result on duplicate job_id (HTTP 200)
    # -----------------------------------------------------------------------
    if job_id in _job_cache:
        cached = _job_cache[job_id]
        replay_resp = cached.model_copy(update={"idempotent_replay": True})
        return JSONResponse(
            status_code=200,
            content=replay_resp.model_dump(mode="json"),
        )

    settings = _get_settings()
    metrics = RequestMetrics(job_id=job_id, shop_id=shop_id, draft_id=draft_id or "")
    pipeline_start = time.perf_counter()

    # -----------------------------------------------------------------------
    # Stage (b): Ingest — decode + resample to 16 kHz mono WAV
    # -----------------------------------------------------------------------
    t0 = time.perf_counter()
    try:
        raw_bytes = await audio.read()
        ingested = process_audio(raw_bytes)
    except AudioTooShortError as e:
        return JSONResponse(status_code=400, content={"code": "audio_too_short", "message": str(e)})
    except AudioTooLongError as e:
        return JSONResponse(status_code=400, content={"code": "audio_too_long", "message": str(e)})
    except BadCodecError as e:
        return JSONResponse(status_code=400, content={"code": "bad_codec", "message": str(e)})
    except AudioIngestError as e:
        return JSONResponse(status_code=400, content={"code": e.code, "message": str(e)})
    metrics.ingest_ms = round((time.perf_counter() - t0) * 1000)

    # -----------------------------------------------------------------------
    # Stage (c): ASR — transcribe audio to Urdu text
    # -----------------------------------------------------------------------
    t0 = time.perf_counter()
    try:
        catalogue = _get_catalogue()
        customers = _get_customers()
        skus = _get_skus()

        asr_payload = _get_asr_service().transcribe(
            audio=ingested,
            job_id=job_id,
            shop_id=shop_id,
            draft_id=draft_id,
            catalogue=skus,
            customers=customers,
            audio_ref=f"audio_{job_id}.wav",
        )
    except Exception as e:
        logger.exception("ASR failed for job_id=%s", job_id)
        return JSONResponse(
            status_code=503,
            content={"code": "asr_unavailable", "message": str(e)},
        )
    metrics.asr_ms = round((time.perf_counter() - t0) * 1000)
    metrics.asr_engine = asr_payload.engine
    metrics.failover_reason = asr_payload.failover_reason

    raw_text = asr_payload.raw_text
    if not raw_text or not raw_text.strip():
        return JSONResponse(
            status_code=400,
            content={"code": "empty_transcript", "message": "ASR returned empty transcript"},
        )

    # -----------------------------------------------------------------------
    # Stage (d): Normalize — fold, parse numbers, units, typed tokens
    # -----------------------------------------------------------------------
    t0 = time.perf_counter()
    token_stream = normalize(raw_text)
    metrics.normalize_ms = round((time.perf_counter() - t0) * 1000)

    # -----------------------------------------------------------------------
    # Stage (e): Extract — order-independent slot filling
    # -----------------------------------------------------------------------
    t0 = time.perf_counter()
    draft = extract(
        tokens=raw_text,
        catalogue=skus,
        customers=customers,
        open_draft=draft_id,
        shop_id=shop_id,
        draft_id=draft_id or f"d_{job_id}",
        job_ids=[job_id],
    )
    metrics.extract_ms = round((time.perf_counter() - t0) * 1000)

    # -----------------------------------------------------------------------
    # Stage (f): Pricing — resolve prices from spoken > catalogue > missing
    # -----------------------------------------------------------------------
    t0 = time.perf_counter()
    draft.items = resolve_prices(draft.items, catalogue)
    # Recompute total after pricing (int PKR — AGENTS.md rule 1)
    draft.computed_total = int(sum(
        it.line_total for it in draft.items if it.line_total is not None
    ))
    metrics.pricing_ms = round((time.perf_counter() - t0) * 1000)

    # -----------------------------------------------------------------------
    # Stage (g): Validation — run V1–V7
    # -----------------------------------------------------------------------
    t0 = time.perf_counter()
    validation_result = validate(
        items=draft.items,
        customer=draft.customer,
        payment_type=draft.payment_type,
        catalogue=catalogue,
        stated_total=draft.stated_total,
        computed_total=draft.computed_total,
    )
    draft.validation = validation_result
    metrics.validation_ms = round((time.perf_counter() - t0) * 1000)

    # -----------------------------------------------------------------------
    # Confidence composition with real ASR confidence
    # -----------------------------------------------------------------------
    asr_conf = asr_payload.asr_confidence
    draft.confidence = compute_confidence(
        items=draft.items,
        customer=draft.customer,
        order_form=draft.order_form,
        validation_passed=validation_result.passed,
        asr_conf=asr_conf,
    )

    # Set path based on validation
    if validation_result.passed:
        draft.path = "fast"
    else:
        draft.path = "manual"  # may be upgraded to "llm" below

    # Store raw ASR text
    draft.raw_texts = [raw_text]

    # -----------------------------------------------------------------------
    # Stage (h): LLM fallback — ONLY when validation.requires_llm is True
    # -----------------------------------------------------------------------
    t0 = time.perf_counter()
    if validation_result.requires_llm:
        llm_provider = get_llm_provider(settings)

        if isinstance(llm_provider, NoLLMProvider):
            # LLM_PROVIDER=none — skip LLM, leave path as "manual"
            draft.path = "manual"
        else:
            repaired_items, computed_total, success = llm_repair(draft, llm_provider)
            if success:
                draft.items = repaired_items
                draft.computed_total = computed_total
                # Re-run the FULL validation gate on LLM output — it never bypasses it
                validation_result = validate(
                    items=draft.items,
                    customer=draft.customer,
                    payment_type=draft.payment_type,
                    catalogue=catalogue,
                    stated_total=draft.stated_total,
                    computed_total=draft.computed_total,
                )
                draft.validation = validation_result
                draft.path = "llm" if validation_result.passed else "manual"
                # Recompute confidence after LLM repair
                draft.confidence = compute_confidence(
                    items=draft.items,
                    customer=draft.customer,
                    order_form=draft.order_form,
                    validation_passed=validation_result.passed,
                    asr_conf=asr_conf,
                )
            else:
                draft.path = "manual"

    metrics.llm_ms = round((time.perf_counter() - t0) * 1000)

    # -----------------------------------------------------------------------
    # Finalize metrics
    # -----------------------------------------------------------------------
    metrics.total_ms = round((time.perf_counter() - pipeline_start) * 1000)
    metrics.path = draft.path
    metrics.order_form = draft.order_form
    metrics.confidence = draft.confidence
    metrics.item_count = len(draft.items)

    # Price source distribution
    for item in draft.items:
        if item.price_source == "spoken":
            metrics.spoken_count += 1
        elif item.price_source == "catalogue":
            metrics.catalogue_count += 1
        else:
            metrics.missing_count += 1

    # Write telemetry
    log_metrics(metrics, log_dir=settings.LOG_DIR)

    # -----------------------------------------------------------------------
    # Build response with ASR engine visibility
    # -----------------------------------------------------------------------
    response = UtteranceResponse(
        **draft.model_dump(),
        asr_engine=asr_payload.engine,
        failover_reason=asr_payload.failover_reason,
    )

    # Cache for idempotency
    _job_cache[job_id] = response

    return JSONResponse(
        status_code=200,
        content=response.model_dump(mode="json"),
    )
