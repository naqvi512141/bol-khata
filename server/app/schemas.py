"""Frozen Pydantic models — single source of truth.

Mirrors docs/02-contracts.md section 1 exactly.
Do not add, remove, or rename a field without asking.
"""

from typing import Literal

from pydantic import BaseModel, Field


# ---------- ASR ----------


class ASRSegment(BaseModel):
    text: str
    start: float
    end: float
    avg_logprob: float
    no_speech_prob: float


class RawASRPayload(BaseModel):
    job_id: str
    shop_id: str
    draft_id: str | None = None
    engine: Literal["groq_whisper", "local_faster_whisper", "model_studio"]
    model_name: str
    language: Literal["ur"] = "ur"
    raw_text: str  # Urdu script, unmodified
    segments: list[ASRSegment] = []
    asr_confidence: float  # 0..1, derived; see section 5
    audio_ref: str
    duration_ms: int
    clip_ratio: float = 0.0
    bias_prompt_hash: str = ""
    processing_ms: int = 0


# ---------- extraction ----------

Unit = Literal["kg", "g", "l", "ml", "dozen", "packet", "bottle", "box", "piece"]


class LineItem(BaseModel):
    sku_id: str | None
    raw_name: str
    display_name: str | None = None
    qty: float | None = None
    unit: Unit | None = None
    spoken_amount: int | None = None  # integer PKR, from MONEY token adjacent to line item
    unit_price: int | None = None  # integer PKR
    line_total: int | None = None  # integer PKR
    price_source: Literal["spoken", "catalogue", "missing"] = "missing"
    match_score: float = 0.0
    match_status: Literal["resolved", "ambiguous", "unknown", "provisional"]
    candidates: list[str] = []
    derived_fields: list[str] = []  # computed, not heard
    token_span: tuple[int, int]


class CustomerRef(BaseModel):
    customer_id: str | None = None
    raw_name: str | None = None  # None when nothing was spoken
    status: Literal["resolved", "ambiguous", "unknown", "absent"]
    confidence: float = 0.0
    candidates: list[str] = []
    source: Literal["spoken", "open_draft", "cash_default"]


class ResidueSpan(BaseModel):
    text: str
    token_span: tuple[int, int]
    adjacent_to_qty_or_unit: bool  # decides product vs name
    interpretation: Literal["customer", "product", "filler", "unresolved"]


class Issue(BaseModel):
    rule: str  # "V1".."V7"
    item_index: int | None = None
    message: str


class ValidationResult(BaseModel):
    passed: bool
    blocking: list[Issue] = []
    warnings: list[Issue] = []
    requires_llm: bool = False


OrderForm = Literal[
    "canonical", "name_last", "name_medial", "no_name_draft", "no_name_cash"
]


class ParsedDraft(BaseModel):
    draft_id: str
    job_ids: list[str]
    shop_id: str
    customer: CustomerRef
    items: list[LineItem]
    residue: list[ResidueSpan] = []
    stated_total: int | None = None  # only if spoken
    computed_total: int  # authoritative
    payment_type: Literal["cash", "udhaar"]
    currency: Literal["PKR"] = "PKR"
    order_form: OrderForm
    confidence: float
    path: Literal["fast", "llm", "manual"]
    validation: ValidationResult
    normalized_tokens: str  # debug + audit
    raw_texts: list[str] = []


# ---------- catalogue ----------


class PricePoint(BaseModel):
    price: int
    qty: float
    observed_at: str


class SKU(BaseModel):
    sku_id: str
    display_name: str
    aliases: list[str] = []
    default_unit: Unit
    unit_price: int | None = None
    price_history: list[PricePoint] = []
    max_plausible_qty: float = 50.0
    provisional: bool = False
    last_sold_at: str | None = None


class Customer(BaseModel):
    customer_id: str
    display_name: str
    aliases: list[str] = []
    phone: str | None = None
    balance: int = 0  # integer PKR
    last_txn_at: str | None = None
