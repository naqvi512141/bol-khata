# PROMPTS — copy-paste, one per IDE conversation

> This file is for the human. The agent should not treat it as instructions.

**How to use:** start a **new conversation** in the IDE for each phase. Paste the
prompt. When the phase's acceptance criteria pass, commit, then start a fresh
conversation for the next phase.

**Why new conversations:** long conversations degrade. The model starts
forgetting earlier rules, contradicting its own decisions, and re-editing
finished files. A fresh conversation re-reads `AGENTS.md` cleanly.

---

## Phase 0 — Orientation

```
Read AGENTS.md, docs/01-domain-urdu.md, docs/02-contracts.md and
docs/03-build-plan.md completely before responding.

Write no code in this response.

Then give me:
1. One paragraph restating what this system does and who uses it.
2. The pipeline stages in order, with the module path for each.
3. Every rule in AGENTS.md section 2 that will constrain the code, and how.
4. Every contradiction, gap or ambiguity you found in the docs. Be specific
   and cite file and section. Do not tell me there are none.
5. A proposed file list for Phase 1 only.
```

**Check the answer before continuing.** It must state that `paun` subtracts, and
that prices are usually not spoken. If it misses either, say so and ask it to
re-read `docs/01-domain-urdu.md` §4 and `docs/02-contracts.md` §6. If it gets
those wrong now, it will get them wrong in code.

---

## Phase 1 — Scaffold and data

```
Implement Phase 1 from docs/03-build-plan.md. Scaffold and data only, no
pipeline logic.

Constraints:
- app/schemas.py must match docs/02-contracts.md section 1 exactly. Same field
  names, same types, same defaults. Do not add fields.
- client/src/types.ts must mirror docs/02-contracts.md section 2 exactly.
- Money fields are int. Never float.
- Demo data must include the five multi-token SKU names listed in
  docs/01-domain-urdu.md section 9, and the deliberate near-duplicate customer
  names.
- fixtures.ts needs all eight cases listed in the Phase 1 deliverables.

When done, print the exact commands I should run to verify, then stop.
```

---

## Phase 2 — Normalizer

```
Implement Phase 2 from docs/03-build-plan.md: server/app/normalizer/ and its
tests only. Touch nothing else.

Write the tests FIRST, in server/tests/normalizer/, using the expected values in
docs/01-domain-urdu.md section 8. Show me the test file and stop. Do not write
the implementation until I say continue.

Rules:
- Expected values in the docs are authoritative. If a test fails, the
  implementation is wrong, not the test.
- Every Urdu string comes from docs/01-domain-urdu.md. Invent nothing.
- Lexicons are data (dicts or JSON), never conditions inside if branches.
- paun subtracts 0.25. paun chaar kilo is 3.75.
- Fully type annotated; mypy --strict must pass on this package.
```

Then, after reviewing the tests:

```
Continue. Implement the normalizer so those tests pass. Do not modify any test.
```

---

## Phase 3 — Extractor

```
Implement Phase 3 from docs/03-build-plan.md: server/app/extractor/ and its
tests only.

This is the highest-risk module in the project. Read docs/02-contracts.md
section 3 twice before starting.

Write the tests FIRST from the extractor table in docs/01-domain-urdu.md
section 8, then stop and show me. Do not implement yet.

Hard requirements:
- Six passes exactly as specified. No pass may reference an absolute token
  position. Adjacency is allowed; position is not. If you write tokens[0] or
  tokens[-1] to identify a role, you have violated the design.
- n-gram matching: spans of 3 tokens, then 2, then 1. Longest match wins and
  claims its tokens. "laal mirch" is one item.
- Matching needs a score threshold AND a margin over the runner-up. Thresholds
  are in docs/02-contracts.md section 4. Do not change them.
- The same basket in four word orders must produce identical items. That is the
  central test.
- Two isolated residue spans is blocking, not a guess.
```

Then:

```
Continue. Implement the six passes so the tests pass. Do not modify any test.
After the implementation, run:
  grep -rn "tokens\[0\]\|tokens\[-1\]" app/extractor/
and show me the output. It should be empty.
```

---

## Phase 4 — Pricing and validation

```
Implement Phase 4 from docs/03-build-plan.md: server/app/pricing/ and
server/app/validation/ plus tests. Touch nothing else.

Rules:
- Price priority is exactly: spoken > catalogue lookup > missing. See
  docs/02-contracts.md section 6.
- V1 is SKIPPED when stated_total is None. Most real utterances have no spoken
  total. Do not treat a missing total as a failure.
- V3 is the most important rule. Test it with a deliberate 10x price error
  (300 becomes 3000) and prove it fires.
- requires_llm is False when the only blocking issues are V6 or V7. Those need
  a human, not a model.
- No float anywhere in the money path. Round once, at computation, and store.

Write a test that fails for each of V1 through V7 individually and passes when
the input is clean.
```

---

## Phase 5 — ASR service

```
Implement Phase 5 from docs/03-build-plan.md: server/app/asr/ and
server/app/ingest/.

Read docs/04-stack.md sections 3 and 4 for the exact call shapes.

Rules:
- Groq whisper-large-v3 is primary; local faster-whisper small int8 is the
  fallback. Selected by the ASR_ENGINE env var, with automatic failover.
- language="ur", task="transcribe". NEVER task="translate".
- On the local path, condition_on_previous_text=False.
- Do not log or print the API key, not even truncated.
- The bias prompt must stay under about 200 tokens. Build it from the fixed
  numeral lexicon plus top SKUs by recency-weighted frequency plus active
  customer names. Write a test asserting the cap.
- Reject audio shorter than 700 ms or longer than 20 s with a typed error.

The engine actually used must be recorded in RawASRPayload.engine.
```

---

## Phase 6 — API and LLM fallback

```
Implement Phase 6 from docs/03-build-plan.md: the /v1/utterance endpoint wiring
the full pipeline, plus server/app/llm/ and server/app/telemetry/.

Rules:
- Idempotent on job_id. A repeated job_id returns the cached ParsedDraft and
  must never reprocess.
- The LLM is invoked ONLY when validation.requires_llm is True.
- LLM output is re-run through the FULL validation gate. It never bypasses it.
- temperature 0, JSON mode, strip markdown code fences regardless, validate
  with Pydantic, one retry with the validation error appended, then set
  path="manual" and give up.
- LLM_PROVIDER=none must be a valid configuration. The app runs with no LLM.
- Telemetry: one JSON line per request with per-stage timings, path,
  order_form, price_source distribution and confidence.
```

---

## Phase 7 — Client

```
Implement Phase 7 from docs/03-build-plan.md: client/src/ only. No server
changes.

Rules:
- Push-to-talk only. No always-on listening, no wake word.
- A ULID is generated at button release and travels with the job. The customer
  identity lives in the audio, not in component state. There must be no
  "currently selected customer" variable.
- Job queue in Dexie, max 3 requests in flight, exponential backoff, survives a
  page reload.
- Draft basket: 20 second window, further utterances append, large discard
  control. No voice cancel commands.
- Dexie only. No localStorage, no sessionStorage.
- Confidence bands and the review tray exactly as docs/02-contracts.md section 5
  specifies. Chime immediately; full spoken readback only when the queue is
  empty.
- 3 second undo on every auto-commit. Not optional.
- Balances are computed as a fold over events, never stored.
- Every component under 200 lines.

Build against client/src/fixtures.ts first, then switch to the real endpoint.
```

---

## Phase 8 — TTS bank and measurement

```
Implement Phase 8 from docs/03-build-plan.md.

1. scripts/build_tts_bank.py using edge-tts, voice ur-PK-UzmaNeural, generating
   cardinals 0-99, multipliers, fractions, units, frame phrases and three
   chimes into client/public/tts/. Run offline once; the runtime must never
   call edge-tts.
2. scripts/run_corpus.py to run the whole corpus end to end and print a metrics
   table: WER with and without the bias prompt, fast-path percentage, p50 and
   p95 latency per stage, SKU and customer match accuracy, normalizer accuracy
   on the fraction subset, extractor accuracy broken down PER order_form, and
   price-source distribution.

Report real measured numbers. Do not estimate, extrapolate, or fill gaps with
plausible values. If a metric cannot be computed, print "not measured" and say
why.
```

---

## Recovery prompts

**When it drifts from the rules:**
```
Stop. Re-read AGENTS.md section 2 and tell me which rule the code you just
wrote violates. Fix only that, and change nothing else.
```

**When it edits files outside scope:**
```
You modified files outside this phase's scope. List every file you touched,
revert the out-of-scope ones, and continue with the phase scope only.
```

**When a test fails and it wants to change the test:**
```
The expected values in docs/01-domain-urdu.md are authoritative. Do not modify
the test. Fix the implementation.
```

**When it invents Urdu vocabulary:**
```
You added an Urdu string that is not in docs/01-domain-urdu.md. Remove it. If
the lexicon genuinely needs that entry, tell me which word and why, and I will
verify it with a native speaker before you add it.
```

**When it wants to use an LLM for the main path:**
```
The deterministic path handles the majority of utterances. The LLM is a
fallback for validation-gate failures only. See AGENTS.md section 9. Revert
that change.
```

**When it goes badly wrong:**
Do not ask it to patch its way out. `git reset --hard` to the last good commit,
start a fresh conversation, and re-run the phase prompt with an added line
saying what went wrong last time.
