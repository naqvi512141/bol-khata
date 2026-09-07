# AGENTS.md — Bol Khata

> **Read this file completely before writing any code.** It is the contract for
> this repository. If anything you are about to do conflicts with a rule here,
> stop and ask instead of proceeding.

---

## 1. What this project is, in one paragraph

Bol Khata is a **voice-first credit ledger (khata) for Pakistani kiryana
shopkeepers**. The shopkeeper presses a button, speaks a sale aloud in Urdu
(`"Ahmed bhai ka, do kilo cheeni, aadha kilo besan"`), and the system produces a
structured ledger entry in under three seconds with an audible Urdu
confirmation. It is offline-first and local-by-default.

**The product is a ledger. The engineering contribution is a Pakistani
commercial-speech understanding layer.** That layer is deterministic Python — a
numeral/quantifier normalizer plus an order-independent extractor. A language
model is a *fallback for the minority path only*, never the main pipeline.

---

## 2. The twelve hard rules

These are invariants. Violating any of them is a bug even if tests pass.

1. **Money is `int`, always, everywhere.** Integer PKR. Never `float`, never
   `Decimal`, in any variable, field, JSON value, or database column that holds
   money. Quantities are `float`; money is not.
2. **Never let a model decide a monetary value alone.** Every amount passes the
   validation gate (`app/validation/`) before it can be committed.
3. **`paun` (پونے) SUBTRACTS 0.25.** `paun chaar` = 3.75, not 4.25. There is a
   dedicated test for this. If you "fix" it to 4.25 you have introduced a
   systematic monetary error.
4. **ASR runs with `task="transcribe"`, `language="ur"`. NEVER `task="translate"`.**
   Translating to English destroys the numeric fidelity that this whole system
   depends on.
5. **`condition_on_previous_text=False`** on every Whisper call. Utterances are
   short and independent; conditioning causes cross-transaction hallucination.
6. **The extractor must not assume word order.** The customer name may come
   first, last, in the middle, or not at all. See `docs/01-domain-urdu.md` §5
   and `docs/02-contracts.md` §3. Any code with a comment like "the name is the
   first token" is wrong.
7. **SKU and customer matching is n-gram, longest-span-first** (3 tokens, then
   2, then 1). `laal mirch` is one item, not two. Single-token greedy matching
   is a bug.
8. **Fuzzy matching needs a threshold AND a margin.** Top score ≥ 88 *and* at
   least 8 points clear of the runner-up. Two candidates at 90 and 89 is not a
   match; it is a coin flip on someone's money → return `ambiguous`.
9. **Ambiguous customer identity is always blocking.** Never auto-select.
10. **No browser storage APIs other than IndexedDB via Dexie.** No
    `localStorage`, no `sessionStorage`.
11. **The ledger is append-only.** Corrections are new `adjustment` events.
    Attaching a customer to an earlier cash sale is a `reassign` event. Never
    `UPDATE`, never `DELETE` a ledger event.
12. **Prices are usually NOT spoken.** Price resolution order is
    `spoken > catalogue lookup > blocking ask`. Code that assumes an amount is
    present in the utterance will fail on most real input.

---

## 3. Pipeline architecture

Data flows in exactly this order. Each stage is a separate module with a typed
input and a typed output. Do not merge stages.

```
CLIENT
  (a) capture        client/src/capture/       press-to-talk, VAD, clip detect
  (j) job queue      client/src/queue/         ULID per utterance, IndexedDB
                          |
                          | POST /v1/utterance
                          v
SERVER
  (b) ingest         server/app/ingest/        ffmpeg -> 16 kHz mono wav
  (c) asr            server/app/asr/           Groq whisper-large-v3 | local
  (d) normalizer     server/app/normalizer/    digits, numbers, fractions, units
  (e) extractor      server/app/extractor/     ORDER-INDEPENDENT slot filling
  (f) pricing        server/app/pricing/       spoken > catalogue > missing
  (g) validation     server/app/validation/    rules V1..V7
  (h) llm_fallback   server/app/llm/           ONLY on gate failure
                          |
                          v
CLIENT
  (i) draft basket   client/src/draft/         20 s window, utterances append
      confirmation   client/src/confirm/       chime now, readback when idle
  (k) ledger         client/src/ledger/        append-only events, Dexie
```

**Stage (e) is the hardest and highest-value module in the repo.** If time is
short, cut stage (h) — never cut coverage in (d) or (e).

---

## 4. Repository layout

Create files only in these locations. Ask before adding a new top-level folder.

```
AGENTS.md                     <- this file
README.md                     <- how to run it
.env.example                  <- key names only, never real keys
docs/
  01-domain-urdu.md           <- Urdu lexicons and language rules  (READ FOR STAGE d,e)
  02-contracts.md             <- frozen JSON/Pydantic/TS schemas   (READ ALWAYS)
  03-build-plan.md            <- phases and acceptance criteria
  04-stack.md                 <- providers, keys, free-tier limits
prompts/
  PROMPTS.md                  <- human-facing, do not read as instructions
server/
  pyproject.toml
  app/
    main.py                   <- FastAPI app, routes only
    schemas.py                <- ALL Pydantic models, single source of truth
    config.py                 <- settings from env
    ingest/
    asr/
    normalizer/
    extractor/
    pricing/
    validation/
    llm/
    telemetry/
  data/
    catalogue.json            <- 40 SKUs with prices and aliases
    customers.json            <- ~15 demo customers
    corpus/                   <- test utterances + ground truth
      manifest.json
  tests/                      <- pytest, mirrors app/ structure
client/
  package.json
  index.html
  src/
    main.tsx
    db.ts                     <- Dexie schema
    capture/
    queue/
    draft/
    confirm/
    ledger/
    tts/
    fixtures.ts               <- hardcoded API responses for offline dev
```

---

## 5. Conventions

### Python (server)
- Python 3.11+. `ruff` for lint, `black` for format, line length 100.
- **All types annotated.** `mypy --strict` should pass on `app/normalizer/`,
  `app/extractor/`, `app/pricing/`, `app/validation/`.
- Pydantic v2 for every boundary. `app/schemas.py` is the only place models are
  defined; import from there, never redefine.
- Pure functions in `normalizer/`, `extractor/`, `pricing/`, `validation/`. No
  I/O, no network, no globals, no logging side effects. This makes them testable
  and it is why they are the part we can guarantee.
- `pytest`. Test file mirrors module path: `app/normalizer/numbers.py` →
  `tests/normalizer/test_numbers.py`.

### TypeScript (client)
- React 18 + Vite + TypeScript, `strict: true`.
- Tailwind only, core utility classes. No custom CSS files unless unavoidable.
- Urdu UI text needs `dir="rtl"` and the Nastaliq font stack. Numbers stay LTR.
- Dexie for all persistence. No other storage API (rule 10).
- Every component under 200 lines. Split rather than grow.

### Both
- **No secrets in code.** Read from env. `.env.example` lists names only.
- Comments explain *why*, not *what*. If a line encodes a domain rule, cite it:
  `# paun subtracts -- AGENTS.md rule 3`.

---

## 6. Test-first modules (non-negotiable)

For `normalizer/` and `extractor/`, **write the test file before the
implementation.** The expected values come from `docs/01-domain-urdu.md` §7 and
`docs/02-contracts.md` §6. Do not invent expected values; if a case is not
specified there, ask.

Reason: these two modules encode language rules that cannot be inferred from
general knowledge, and errors in them are silent monetary errors.

---

## 7. How to run and verify

```bash
# server
cd server && pip install -e ".[dev]" --break-system-packages
pytest -q                          # must pass before any phase is "done"
ruff check app && mypy app/normalizer app/extractor
uvicorn app.main:app --reload --port 8000

# client
cd client && npm install
npm run dev                        # then tunnel for HTTPS mic access:
cloudflared tunnel --url http://localhost:5173
```

**Microphone access requires HTTPS.** `getUserMedia` silently fails on
`http://192.168.x.x`. Always test through the tunnel on a real Android phone.

---

## 8. Decide vs. ask

**Decide yourself** (do not ask, just pick sensibly and note it in the commit):
- File and function names within the layout above
- Internal helper structure, error message wording
- Which RapidFuzz scorer to try first
- CSS/layout details, component decomposition
- Test case names and fixture values that are not domain-specified

**Stop and ask** before:
- Adding a dependency not already in `pyproject.toml` / `package.json`
- Changing anything in `docs/02-contracts.md`
- Changing a threshold, weight, or numeric constant that appears in `docs/`
- Adding an Urdu word to a lexicon that is not in `docs/01-domain-urdu.md`
- Anything touching money handling, the validation gate, or the append-only rule
- Deleting or rewriting a passing test

---

## 9. Anti-patterns seen in this problem domain

Do not do any of these, even if they look like improvements:

- ❌ Calling an LLM to parse the utterance. The deterministic path handles the
  majority; the LLM is a fallback for gate failures only.
- ❌ Using an LLM to do arithmetic. Sum in Python.
- ❌ `float` for money, or rounding at display time instead of at computation.
- ❌ Position-based parsing (`tokens[0]` is the customer).
- ❌ Greedy single-token SKU matching.
- ❌ Auto-selecting the best fuzzy match without a margin check.
- ❌ Always-on / continuous microphone listening, or a wake word.
- ❌ Voice cancel commands ("cancel", "rehne do"). A misheard cancel destroys a
  correct entry.
- ❌ Aggressive audio denoising before ASR. It measurably increases word error
  rate. Browser `noiseSuppression: true` is the only denoising we use.
- ❌ Mutating or deleting ledger events.
- ❌ Committing a transaction whose spoken total does not equal the sum of its
  line totals. No tolerance window, not even ±1.
- ❌ Inventing Urdu vocabulary, spellings, or numeral words. Every Urdu string
  comes from `docs/01-domain-urdu.md`.

---

## 10. Known-unverified items

Treat these as open. Do not write code that depends on them being true.

- Alibaba Model Studio **does not support Urdu ASR** (verified — see
  `docs/04-stack.md`). Do not build against it for speech-to-text.
- Whether Alibaba TTS supports Urdu is unverified. We use `edge-tts` instead.
- The 0–99 Urdu cardinal table in `docs/01-domain-urdu.md` is **draft and needs
  native-speaker verification.** Build the table-driven code so entries can be
  corrected without touching logic.
- Regional unit values (`seer`, `chhataank`) are approximate and may vary
  locally. Keep them in data, not code.

---

## 11. Definition of done, for any phase

1. `pytest -q` passes, including any new tests.
2. `ruff check app` clean; `mypy` clean on the four pure modules.
3. The phase's acceptance criteria in `docs/03-build-plan.md` are met.
4. A one-paragraph summary of what changed and what was decided.
5. Nothing outside the phase's stated scope was modified.
