# 03 — Build Plan

Eight phases. **One phase per IDE conversation.** Each phase has explicit
acceptance criteria and a verification command the human runs before moving on.

Do not start a phase until the previous one's criteria are met and committed.

---

## Phase 0 — Orientation (no code)

**Agent task:** read `AGENTS.md`, `docs/01-domain-urdu.md`, `docs/02-contracts.md`,
this file. Then produce:

1. A one-paragraph restatement of what the system does.
2. The pipeline stages in order, with the module path for each.
3. A list of every rule in `AGENTS.md` §2 that constrains the code you will
   write, and how.
4. Any contradictions, gaps, or ambiguities you found in the docs.
5. A proposed file list for Phase 1 only.

**Accept when:** the restatement is accurate, the agent has correctly identified
that `paun` subtracts and that prices are usually not spoken, and item 4 is
non-empty (there are always gaps; an agent that finds none has not read
carefully).

**Write no code in this phase.**

---

## Phase 1 — Scaffold and data

**Scope:** repo skeleton, dependency manifests, demo data, no logic.

Deliverables:
- `server/pyproject.toml` with: `fastapi`, `uvicorn`, `pydantic>=2`,
  `python-multipart`, `rapidfuzz`, `httpx`, `python-ulid`;
  dev extras `pytest`, `ruff`, `black`, `mypy`.
- `server/app/schemas.py` — **exactly** the models in `docs/02-contracts.md` §1.
- `server/app/config.py` — settings from env (`GROQ_API_KEY`,
  `ASR_ENGINE`, `LLM_PROVIDER`, `SHOP_ID`).
- `server/app/main.py` — FastAPI app with only `GET /v1/health`.
- `server/data/catalogue.json` — 40 SKUs per `docs/01` §9, including the five
  multi-token names.
- `server/data/customers.json` — 15 customers with the deliberate near-duplicates.
- `server/data/urdu_numerals.json` — the cardinal table from `docs/01` §3,
  with the gaps present and clearly marked.
- `client/` — Vite + React + TS + Tailwind scaffold, `dir="rtl"`, Nastaliq font
  stack, `src/types.ts` mirroring `docs/02-contracts.md` §2.
- `client/src/fixtures.ts` — **8 hardcoded `ParsedDraft` objects** covering:
  high confidence canonical, medium confidence with a V3 warning, blocking
  ambiguous customer, blocking missing price, `name_last`, `name_medial`,
  `no_name_cash`, and a multi-token SKU.
- `.env.example`, `README.md`, `.gitignore`.

**Accept when:**
```bash
cd server && pytest -q && python -c "import app.schemas"
cd ../client && npm run build
```
both succeed, and `client/src/fixtures.ts` renders in a list view with no
server running.

---

## Phase 2 — Normalizer (test-first)

**Scope:** `server/app/normalizer/` and `server/tests/normalizer/` only.

Write the tests first, from `docs/01-domain-urdu.md` §8. Then implement:

- `folding.py` — `urdu_fold()` per `docs/01` §2
- `numbers.py` — cardinals, multipliers, `parse_number_words()` per §3
- `quantifiers.py` — Class A standalone, Class B modifiers per §4
- `units.py` — `UNITS_CANON`, `paw` disambiguation per §5
- `lexicons.py` — honorifics, genitive markers, fillers, negation, markers per §6
- `tokenize.py` — split, fold, emit the typed token stream
- `__init__.py` — `normalize(text) -> TokenStream`

**Accept when:**
```bash
cd server && pytest tests/normalizer -q -v
mypy app/normalizer --strict
```
All §8 normalizer cases pass, `paun chaar kilo == 3.75`, and `sawa` alone
returns `None`.

---

## Phase 3 — Extractor (test-first)

**Scope:** `server/app/extractor/` and its tests only. **The hardest phase.**

Write tests first from `docs/01` §8 extractor table. Then implement the six
passes from `docs/02-contracts.md` §3:

- `matching.py` — `match_sku()`, `match_customer()`, threshold + margin,
  frequency and recency priors
- `ngram.py` — longest-span-first n-gram scanning
- `grouping.py` — adjacency-based line-item grouping
- `residue.py` — residue collection and attribution rules
- `__init__.py` — `extract(tokens, catalogue, customers, open_draft) -> ParsedDraft`

**Accept when:**
```bash
cd server && pytest tests/extractor -q -v
```
- The same basket in **four word orders** yields identical `items`.
- `aik paw laal mirch` yields **one** item.
- Two isolated residue spans → blocking.
- No-name with no draft → `payment_type="cash"`, `order_form="no_name_cash"`.
- Unknown token adjacent to a qty → provisional SKU, not a customer.
- `grep -rn "tokens\[0\]" app/extractor/` returns nothing.

---

## Phase 4 — Pricing and validation

**Scope:** `server/app/pricing/`, `server/app/validation/`, tests.

- `pricing/resolver.py` — three-tier priority per `docs/02` §6
- `pricing/catalogue.py` — load JSON, `current_price()`, `median_price()`,
  `observe_price()` with an EWMA
- `validation/rules.py` — V1–V7 per `docs/02` §7, each rule a separate function
- `validation/confidence.py` — composition per `docs/02` §5

**Accept when:** tests prove each of V1–V7 fires on a crafted failing input and
stays silent on a passing one; V1 is **skipped** when `stated_total is None`;
V3 catches a 10× price error; `requires_llm` is `False` when the only blocking
issue is V6 or V7; no `float` appears in any money path
(`grep -rn "float" app/pricing app/validation` reviewed manually).

---

## Phase 5 — ASR service

**Scope:** `server/app/asr/`, `server/app/ingest/`.

- `ingest/audio.py` — ffmpeg in-memory resample to 16 kHz mono s16le; reject
  `< 700 ms` or `> 20 s`
- `asr/base.py` — `ASREngine` protocol
- `asr/groq_whisper.py` — `POST https://api.groq.com/openai/v1/audio/transcriptions`,
  `model=whisper-large-v3`, `language=ur`, `prompt=<bias string>`
- `asr/local_whisper.py` — `faster-whisper small`, int8, with rules 4 and 5 of
  `AGENTS.md` applied
- `asr/bias.py` — build the bias prompt: fixed numeral lexicon + top ~35 SKUs by
  recency-weighted frequency + top ~10 active customer names, capped at ~200 tokens
- `asr/confidence.py` — `avg_logprob` → `asr_conf`

**Accept when:** a real Urdu clip transcribes through the Groq path; killing the
API key falls back to local without an exception; the bias prompt stays under
the token cap; the engine used is recorded in `RawASRPayload.engine`.

---

## Phase 6 — API endpoint and LLM fallback

**Scope:** `server/app/main.py` routes, `server/app/llm/`, `server/app/telemetry/`.

- `POST /v1/utterance` wiring the full pipeline, idempotent on `job_id`
  (in-memory dict is fine for the demo)
- `GET /v1/catalogue/{shop_id}`, `GET /v1/customers/{shop_id}`
- `llm/repair.py` — invoked **only** when `validation.requires_llm`; temperature 0,
  JSON mode, strip code fences, Pydantic-validate, one retry with the error
  appended, then `path="manual"`
- `llm/providers.py` — Groq `qwen/qwen3-32b` primary, Gemini backup, Model Studio
  (Singapore) as the sponsor-demo option; selected by env
- `telemetry/metrics.py` — per-stage timing, `path`, `order_form`,
  `price_source`, confidence, appended as JSON lines to `server/logs/`

**Accept when:** the endpoint returns a valid `ParsedDraft` end to end; the LLM
output is re-run through the validation gate; the LLM is **not** called when the
only blocking issue is V6 or V7; a repeated `job_id` returns the cached result;
telemetry lines are parseable.

---

## Phase 7 — Client: capture, queue, draft, confirmation

**Scope:** `client/src/` only. No server changes.

- `capture/` — push-to-talk, `getUserMedia` per `AGENTS.md` §3, RMS VAD, clip
  detection, codec fallback ladder, Screen Wake Lock
- `queue/` — ULID at button release, Dexie-backed job queue, **max 3 in flight**,
  exponential backoff, survives reload
- `draft/` — 20 s draft window, utterances append, large discard control
- `confirm/` — three confidence bands, field-level highlighting, review tray with
  badge, 3 s undo
- `ledger/` — append-only events, balance as a fold, customer list, day summary
- `tts/` — load the pre-rendered fragment bank, concatenate with a 20 ms
  crossfade, three chimes; full readback only when the queue is empty

**Accept when:** on a real Android phone via `cloudflared`, ten consecutive
recordings all land as separate entries with no mixing; airplane mode queues and
drains on reconnect; a page reload mid-queue loses nothing; the tray badge
increments on a low-confidence result.

---

## Phase 8 — TTS bank, integration, measurement

**Scope:** `scripts/`, integration fixes, metrics harness.

- `scripts/build_tts_bank.py` — `edge-tts`, voice `ur-PK-UzmaNeural`, generating
  cardinals 0–99, multipliers, fractions, units, frame phrases, three chimes,
  into `client/public/tts/`
- `scripts/run_corpus.py` — run the whole corpus end to end and emit the metrics
  table from `AGENTS.md`-adjacent Appendix A: WER with/without bias, fast-path %,
  p50/p95 per stage, SKU and customer accuracy, normalizer fraction accuracy,
  **extractor accuracy per `order_form`**, price-source distribution
- Three-tier fallback ladder verified by physically disconnecting

**Accept when:** `python scripts/run_corpus.py` prints a metrics table with real
measured numbers, and each fallback tier works with the network pulled.

---

## Scope-cut order

If time runs short, cut from the top:

1. LLM fallback (Phase 6 partial) → confirmation tap instead
2. Voice query → button
3. Cloud sync → local only
4. Multi-device → single device

**Never cut:** normalizer, extractor, price resolution, validation gate, audible
readback, 3 s undo, offline ledger commit.
