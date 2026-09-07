# 02 — Frozen Contracts

> **These schemas are frozen.** Do not add, remove, or rename a field without
> asking. The client builds against them from fixtures; the server builds toward
> producing them. That is what lets two developers work in parallel.

---

## 1. Pydantic models — `server/app/schemas.py`

This file is the single source of truth. Every other module imports from it.

```python
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
    raw_text: str                       # Urdu script, unmodified
    segments: list[ASRSegment] = []
    asr_confidence: float               # 0..1, derived; see section 5
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
    spoken_amount: int | None = None               # integer PKR, from MONEY token adjacent to line item
    unit_price: int | None = None                  # integer PKR
    line_total: int | None = None                  # integer PKR
    price_source: Literal["spoken", "catalogue", "missing"] = "missing"
    match_score: float = 0.0
    match_status: Literal["resolved", "ambiguous", "unknown", "provisional"]
    candidates: list[str] = []
    derived_fields: list[str] = []                 # computed, not heard
    token_span: tuple[int, int]

class CustomerRef(BaseModel):
    customer_id: str | None = None
    raw_name: str | None = None                    # None when nothing was spoken
    status: Literal["resolved", "ambiguous", "unknown", "absent"]
    confidence: float = 0.0
    candidates: list[str] = []
    source: Literal["spoken", "open_draft", "cash_default"]

class ResidueSpan(BaseModel):
    text: str
    token_span: tuple[int, int]
    adjacent_to_qty_or_unit: bool                  # decides product vs name
    interpretation: Literal["customer", "product", "filler", "unresolved"]

class Issue(BaseModel):
    rule: str                                      # "V1".."V7"
    item_index: int | None = None
    message: str

class ValidationResult(BaseModel):
    passed: bool
    blocking: list[Issue] = []
    warnings: list[Issue] = []
    requires_llm: bool = False

OrderForm = Literal["canonical", "name_last", "name_medial",
                    "no_name_draft", "no_name_cash"]

class ParsedDraft(BaseModel):
    draft_id: str
    job_ids: list[str]
    shop_id: str
    customer: CustomerRef
    items: list[LineItem]
    residue: list[ResidueSpan] = []
    stated_total: int | None = None                # only if spoken
    computed_total: int                            # authoritative
    payment_type: Literal["cash", "udhaar"]
    currency: Literal["PKR"] = "PKR"
    order_form: OrderForm
    confidence: float
    path: Literal["fast", "llm", "manual"]
    validation: ValidationResult
    normalized_tokens: str                         # debug + audit
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
    balance: int = 0                               # integer PKR
    last_txn_at: str | None = None
```

---

## 2. TypeScript interfaces — `client/src/types.ts`

Mirrors the **client-relevant subset** of section 1. If one changes, both change
in the same commit.

**Server-only fields** (present in the Python model, absent from TS):
- `ParsedDraft.residue` — debug/audit, used only in server telemetry
- `ParsedDraft.normalized_tokens` — debug/audit, the folded token stream
- `ParsedDraft.raw_texts` — debug/audit, original ASR texts per utterance

These are intentionally omitted; the client does not need them.

```ts
export type Unit = 'kg' | 'g' | 'l' | 'ml' | 'dozen' | 'packet'
                 | 'bottle' | 'box' | 'piece';

export type MatchStatus = 'resolved' | 'ambiguous' | 'unknown' | 'provisional';
export type PriceSource = 'spoken' | 'catalogue' | 'missing';
export type OrderForm  = 'canonical' | 'name_last' | 'name_medial'
                       | 'no_name_draft' | 'no_name_cash';

export interface LineItem {
  sku_id: string | null;
  raw_name: string;
  display_name: string | null;
  qty: number | null;
  unit: Unit | null;
  spoken_amount: number | null;     // integer PKR, from MONEY token adjacent to line item
  unit_price: number | null;
  line_total: number | null;
  price_source: PriceSource;
  match_score: number;
  match_status: MatchStatus;
  candidates: string[];
  derived_fields: string[];
  token_span: [number, number];
}

export interface CustomerRef {
  customer_id: string | null;
  raw_name: string | null;
  status: 'resolved' | 'ambiguous' | 'unknown' | 'absent';
  confidence: number;
  candidates: string[];
  source: 'spoken' | 'open_draft' | 'cash_default';
}

export interface ValidationResult {
  passed: boolean;
  blocking: { rule: string; item_index: number | null; message: string }[];
  warnings: { rule: string; item_index: number | null; message: string }[];
  requires_llm: boolean;
}

export interface ParsedDraft {
  draft_id: string;
  job_ids: string[];
  shop_id: string;
  customer: CustomerRef;
  items: LineItem[];
  stated_total: number | null;
  computed_total: number;
  payment_type: 'cash' | 'udhaar';
  order_form: OrderForm;
  confidence: number;
  path: 'fast' | 'llm' | 'manual';
  validation: ValidationResult;
}

// ---------- client-only ----------

export interface CaptureJob {
  job_id: string;                 // ULID, generated at button release
  shop_id: string;
  draft_id: string | null;
  audio_blob_ref: string;
  duration_ms: number;
  peak_rms: number;
  clip_ratio: number;
  codec: string;
  captured_at: string;
  state: 'queued' | 'uploading' | 'processing' | 'done' | 'failed';
  attempts: number;
  result_ref: string | null;
}

export type LedgerEventType =
  | 'sale_udhaar' | 'sale_cash' | 'payment_received'
  | 'adjustment'  | 'reassign'
  | 'customer_created' | 'sku_created' | 'price_updated';

export interface LedgerEvent {
  event_id: string;               // ULID
  shop_id: string;
  device_id: string;
  lamport: number;
  type: LedgerEventType;
  customer_id: string | null;     // null for an unattributed cash sale
  amount: number;                 // signed integer PKR: +debt, -payment
  items: LineItem[];
  payload: Record<string, unknown>;
  corrects_event_id: string | null;
  audio_refs: string[];
  source: 'voice' | 'manual' | 'llm_repair';
  confidence: number;
  created_at: string;
  server_received_at: string | null;
  sync_state: 'pending' | 'in_flight' | 'synced' | 'failed';
  sync_attempts: number;
}
```

---

## 3. The extractor algorithm — six passes, order-independent

**No pass may reference an absolute position.** Adjacency is allowed; position
is not.

```
PASS 1  label closed classes   numbers, quantifiers, units, currency,
                               fillers, honorifics, genitive markers
                               -> finite sets from docs/01, position independent

PASS 2  n-gram SKU match       spans of 3 tokens, then 2, then 1
                               LONGEST MATCH FIRST
                               skip any span already labelled

PASS 3  n-gram customer match  same mechanism, customer list
                               CONSUMES both resolved AND ambiguous matches
                               (prevents half-matched names being re-read as
                               products). Span must carry match_status.

PASS 4  group line items       QTY / UNIT / ITEM / MONEY tokens that are
                               ADJACENT form one line item

PASS 5  collect residue        any span not absorbed by a line item,
                               plus unlabelled tokens

PASS 6  attribute residue      residue is the customer, wherever it sat.
                               Propagate the Span's match_status into
                               CustomerRef.status. An ambiguous status then
                               blocks via V6 as intended.
```

`Span` must carry `match_status: Literal["resolved", "ambiguous"]` so that
Pass 6 can propagate it into `CustomerRef.status` without re-running the
match. An ambiguous customer consumed in Pass 3 still blocks via V6.

```python
from dataclasses import dataclass

@dataclass
class Span:
    start: int
    end: int
    label: str                          # "ITEM" | "CUST"
    ref_id: str | None
    score: float
    match_status: str = "resolved"      # "resolved" | "ambiguous"

def extract(tokens: list[str],
            catalogue: list[SKU],
            customers: list[Customer],
            open_draft: str | None = None) -> ParsedDraft:
    labels: list[str | None] = [None] * len(tokens)
    spans: list[Span] = []

    # PASS 1
    for i, t in enumerate(tokens):
        labels[i] = classify_closed_class(t, tokens, i)   # may return None

    # PASS 2 -- SKU n-grams, longest first
    for n in (3, 2, 1):
        for i in range(len(tokens) - n + 1):
            if any(labels[i:i + n]):
                continue
            m = match_sku(" ".join(tokens[i:i + n]), catalogue)
            if m.status == "resolved":
                for j in range(i, i + n):
                    labels[j] = "ITEM"
                spans.append(Span(i, i + n, "ITEM", m.sku_id, m.score))

    # PASS 3 -- customer n-grams, longest first
    # Consumes BOTH resolved and ambiguous to prevent re-reading as product.
    # Span.match_status records which, for Pass 6 to propagate.
    for n in (3, 2, 1):
        for i in range(len(tokens) - n + 1):
            if any(labels[i:i + n]):
                continue
            m = match_customer(" ".join(tokens[i:i + n]), customers)
            if m.status in ("resolved", "ambiguous"):
                for j in range(i, i + n):
                    labels[j] = "CUST"
                spans.append(Span(i, i + n, "CUST", m.customer_id, m.score,
                                  match_status=m.status))

    # PASS 4
    lines, consumed = group_line_items(tokens, labels, spans)

    # PASS 5
    residue = collect_residue(tokens, labels, spans, consumed)

    # PASS 6 -- propagate Span.match_status into CustomerRef.status
    customer, order_form = attribute_customer(residue, labels, lines, spans, open_draft)

    return build_parsed_draft(customer, lines, residue, order_form, tokens)
```

### Residue attribution rules

| Residue characteristic | Interpretation |
|---|---|
| Adjacent to a QTY or UNIT token | Unknown **product** → provisional SKU |
| Isolated, or adjacent to a genitive marker / honorific | **Customer** candidate |
| Matches the customer list, score ≥ 75, margin ≥ 10 | Customer, `resolved` |
| Matches the customer list, margin < 10 | Customer, `ambiguous` → **blocking** |
| Matches nothing, isolated | New-customer candidate → one-tap add |
| **Two or more** isolated residue spans | **Blocking.** Never guess which is the customer |

### No residue at all

| Situation | Behaviour | `order_form` | `customer.source` |
|---|---|---|---|
| A draft is open | Append to that draft | `no_name_draft` | `open_draft` |
| No draft open | **Default to a cash sale** | `no_name_cash` | `cash_default` |

The cash default never blocks the counter. A customer can be attached later via
a `reassign` event.

### Order-form confidence penalty

```python
ORDER_PENALTY = {
    "canonical":     1.00,
    "name_last":     0.92,
    "name_medial":   0.88,
    "no_name_draft": 0.95,
    "no_name_cash":  0.85,
}
confidence *= ORDER_PENALTY[order_form]
```

---

## 4. Matching thresholds

```python
# SKU
SKU_ACCEPT_SCORE  = 88     # top score required to resolve
SKU_MARGIN        = 8      # points clear of the runner-up
SKU_AMBIGUOUS_MIN = 70     # below this -> unknown, not ambiguous
SKU_FREQ_PRIOR    = 0.05   # score *= 1 + 0.05 * log1p(sale_count)

# Customer
CUST_ACCEPT_SCORE = 75
CUST_MARGIN       = 10     # wider: a wrong customer is the worst failure
CUST_RECENCY_HALF_LIFE_DAYS = 21
CUST_OPEN_BALANCE_BOOST     = 1.15
```

Scorer: `rapidfuzz.fuzz.WRatio` first. Evaluate `token_set_ratio` and
Jaro-Winkler on the corpus and keep whichever wins per token-length bucket.

---

## 5. Confidence composition

```python
asr_conf = math.exp(min(avg_logprob, 0.0))          # (0, 1]
if no_speech_prob > 0.6:
    asr_conf *= 0.3

price_source_score = {"spoken": 1.0, "catalogue": 0.8, "missing": 0.0}

# NOTE: match_score defaults —
#   provisional SKUs: match_score = 0.3
#   unknown SKUs:     match_score = 0.0
# No matched SKUs must LOWER confidence, not leave it at maximum.
confidence = (0.35 * asr_conf
            + 0.20 * min([i.match_score for i in items] or [0.0])
            + 0.20 * customer_conf
            + 0.10 * price_source_score[worst_price_source]
            + 0.15 * (1.0 if validation.passed else 0.0))

confidence *= ORDER_PENALTY[order_form]
```

`min()` over SKU scores is deliberate — one badly matched item should drag the
whole basket into confirmation.

| Band | Behaviour |
|---|---|
| `≥ 0.85` and no blocking issues | Chime, auto-commit, 3 s undo window |
| `0.60 – 0.85` | Committed but flagged; only V3/V4 fields highlighted |
| `< 0.60`, or any blocking issue | Held in the review tray, no auto-commit |

---

## 6. Price resolution

```python
def resolve_price(line: LineItem, catalogue: Catalogue) -> LineItem:
    if line.spoken_amount is not None:
        line.line_total   = line.spoken_amount      # int PKR
        line.price_source = "spoken"
        catalogue.observe_price(line.sku_id, line.spoken_amount, line.qty)
        return line

    unit_price = catalogue.current_price(line.sku_id)
    if unit_price is not None:
        line.unit_price   = unit_price
        line.line_total   = round(unit_price * (line.qty or 1))
        line.price_source = "catalogue"
        line.derived_fields.append("line_total")
        return line

    line.price_source = "missing"                   # -> rule V7, blocking
    return line
```

---

## 7. Validation rules V1–V7

| ID | Rule | Severity | On failure |
|---|---|---|---|
| V1 | `sum(line_totals) == stated_total`. **Skipped when `stated_total is None`** | Blocking | Route to LLM, then confirm |
| V2 | `round(qty * unit_price) == line_total` when all three present | Blocking | Highlight the line |
| V3 | `line_total` within `[0.6×, 1.7×]` of `SKU median × qty`. **Median** = median of the last 10 price observations. **Skipped** when fewer than 3 observations exist (no reliable baseline). | Warning | Highlight price field |
| V4 | `qty <= sku.max_plausible_qty` | Warning | Highlight qty field |
| V5 | Every monetary value `> 0` and an `int` | Blocking | Reject, re-record |
| V6 | `customer.status == "resolved"` OR `payment_type == "cash"` | Blocking | Disambiguation sheet |
| V7 | No line has `price_source == "missing"` | Blocking | Ask for the amount |

`requires_llm` is `True` when there is at least one blocking issue **and** none
of them is V6 or V7 (those need a human, not a model).

**V3 is the most important rule.** It catches order-of-magnitude recognition
errors (300 heard as 3000) that are arithmetically self-consistent. With V1
often skipped (prices usually are not spoken), V3 is frequently the only
automated guard between a bad number and the ledger.

### V3 median specification

- `observe_price(sku_id, amount, qty)` appends to `price_history`.
- `median_price(sku_id)` returns the **median** of the last 10 entries, or
  `None` if fewer than 3 exist.
- When `median_price` returns `None`, V3 is **skipped** for that line (no
  baseline to compare against).
- **Do not use EWMA.** Reason: V3 exists to catch outliers, and an EWMA is
  dragged by the outlier it is meant to catch — one 10× error would raise the
  baseline and make the next 10× error look normal. A median is robust to
  exactly that.

---

## 8. HTTP API

### `POST /v1/utterance`

`multipart/form-data`

| Field | Type | Notes |
|---|---|---|
| `audio` | file | Opus/WebM blob |
| `shop_id` | string | selects catalogue + customer list |
| `job_id` | string | ULID from the client. **Idempotency key** |
| `draft_id` | string \| null | if a draft is open |
| `captured_at` | string | ISO 8601 |
| `client_meta` | JSON string | `{codec, duration_ms, peak_rms, clip_ratio}` |

**200** → `ParsedDraft`
**400** → `{code, message}` for `audio_too_short`, `audio_too_long`, `bad_codec`
**409** → returns the original `ParsedDraft` for a duplicate `job_id`
**503** → `{code: "asr_unavailable"}` → client falls back to manual entry

Retrying the same `job_id` **must return the cached result, never reprocess.**

### Other endpoints

```
GET  /v1/catalogue/{shop_id}     -> list[SKU]
GET  /v1/customers/{shop_id}     -> list[Customer]
POST /v1/query                   -> VoiceQueryResponse   (balance lookups)
POST /v1/sync/events             -> idempotent batch upsert, keyed on event_id
GET  /v1/health                  -> {status, asr_engine, version}
```

---

## 9. Client Dexie schema

```ts
db.version(1).stores({
  jobs:      'job_id, state, created_at',
  drafts:    'draft_id, customer_id, opened_at',
  events:    'event_id, shop_id, customer_id, created_at, sync_state',
  customers: 'customer_id, folded_name, last_txn_at',
  skus:      'sku_id, folded_name, *aliases, provisional',
  prices:    '[sku_id+observed_at]',
  audio:     'job_id',                    // Blob, LRU-evicted
  outbox:    '++seq, event_id, attempts, next_retry_at',
});
```

**Balances are never stored.** `balance(customer)` is computed as a fold over
`events`: `sum(udhaar amounts) - sum(payments)`. This is what makes corrections
and multi-device sync work without conflict resolution.
