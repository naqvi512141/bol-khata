# 04 — Stack, Providers and Keys

Distilled from research done September 2026. **Free-tier limits change without
notice** — treat every number here as "check the console on Day 1", not as a
guarantee to code against.

---

## 1. Decisions already made — do not re-litigate

| Layer | Use | Why |
|---|---|---|
| ASR primary | **Groq `whisper-large-v3`** | Free, hosted, fast, and Whisper's training data includes Urdu |
| ASR fallback | **`faster-whisper` small, int8, local** | Runs with Wi-Fi off; proves the offline story |
| LLM fallback | **Groq `qwen/qwen3-32b`**, JSON mode, temp 0 | Free, fast, Qwen weights keep the sponsor story intact |
| LLM backup | **Google AI Studio `gemini-2.5-flash`** | Higher free quota if Groq's is exhausted during testing |
| LLM sponsor demo | **Alibaba Model Studio (DashScope), Singapore region** | Free token grant. Wire it up and show it working, even if it carries no real traffic |
| TTS | **`edge-tts`**, `ur-PK-UzmaNeural` / `ur-PK-AsadNeural` | Real Pakistani Urdu voices, no key, free |
| Tunnel | **cloudflared** | Free, stable, needed for HTTPS mic access |
| Local DB | **Dexie / IndexedDB** | Local-first is a design principle, not a fallback |
| Mirroring | **scrcpy** | Free, near-zero-lag Android mirroring for the demo |

---

## 2. Alibaba Cloud does NOT support Urdu ASR — verified

Do not build speech-to-text against it, and do not spend Day 1 testing it.

- **Qwen3-ASR-Flash** (hosted DashScope): 11 languages — Chinese, English,
  Arabic, French, German, Spanish, Italian, Portuguese, Russian, Japanese,
  Korean. **No Urdu.**
- **Qwen3-ASR-1.7B / 0.6B** (open weights): ~52 languages/dialects including
  **Hindi**, Persian, Turkish, Indonesian and others. **Urdu is not among them.**
  An open upstream issue requesting Urdu is unresolved.
- **Paraformer**: Chinese-focused, no Urdu.

**How to use this finding.** Present it as a real technical result, paired with
the production path (`PAI-EAS` serving a fine-tuned Whisper) and a
cost-per-transaction figure. A measured gap in a sponsor's regional coverage is
more interesting to a technical judge than a fudged benchmark.

Alibaba **is** still used for: the LLM fallback demo (Model Studio, Singapore),
and OSS / RDS / Function Compute / ECS if hackathon credits land.

---

## 3. Environment variables

`.env.example` — names only, never real values.

```bash
# --- ASR ---
ASR_ENGINE=groq                 # groq | local
GROQ_API_KEY=

# --- LLM fallback ---
LLM_PROVIDER=groq               # groq | gemini | model_studio | none
LLM_MODEL=qwen/qwen3-32b
GEMINI_API_KEY=
DASHSCOPE_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1

# --- app ---
SHOP_ID=demo_shop_01
LOG_DIR=./logs
```

**Rules.** Never commit `.env`. Never print a key, even truncated, in logs or
error messages. `LLM_PROVIDER=none` must be a valid setting — the app has to run
with no LLM at all.

---

## 4. Provider call shapes

### Groq ASR — OpenAI-compatible

```python
files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
data  = {
    "model": "whisper-large-v3",
    "language": "ur",
    "response_format": "verbose_json",   # needed for avg_logprob
    "temperature": 0,
    "prompt": bias_prompt,               # the vocabulary bias string
}
r = httpx.post("https://api.groq.com/openai/v1/audio/transcriptions",
               headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
               files=files, data=data, timeout=30)
```

Note: hosted Whisper exposes no `condition_on_previous_text` flag. Rule 5 in
`AGENTS.md` applies to the **local** `faster-whisper` path, where it must be set
explicitly.

Rough free-tier shape: ~2,000 requests/day, ~20 requests/minute. Ample for a
hackathon. Check your console.

### Groq LLM

Same base URL, `/openai/v1/chat/completions`, `response_format={"type":
"json_object"}`, `temperature=0`.

### Alibaba Model Studio

OpenAI-SDK compatible against `DASHSCOPE_BASE_URL`. **Activate in the Singapore
region** — the free token grant does not apply to other endpoints. Do this the
moment credentials exist, not on demo day.

### edge-tts

```bash
pip install edge-tts --break-system-packages
edge-tts --voice ur-PK-UzmaNeural --text "سات سو بیس" --write-media out.mp3
```

Unofficial wrapper around a Microsoft service. Generate the whole fragment bank
**offline, once**, and commit the audio files. The runtime path must never call
it — if the service changes, a committed bank still works on demo day.

---

## 5. Hosting

**First:** ask the organizers what Alibaba Cloud credits you have. That answer
decides whether ECS / OSS / RDS are free for you.

**If credits are thin or late:** Oracle Cloud Always Free (Ampere A1 ARM,
roughly 2 OCPU / 12 GB RAM, permanent, plus ~200 GB block storage) runs FastAPI
+ ffmpeg + `faster-whisper` int8 comfortably at hackathon traffic. Stay strictly
inside the free shapes.

**Database:** you probably do not need one. Local-first means Dexie carries the
whole MVP. Only stand up Postgres if cloud sync survives the scope cuts.

---

## 6. Day 1 first-hour checklist

1. Get a Groq API key. Send **one real Urdu clip** through `whisper-large-v3`.
   Look hard at the raw output — script, number formatting, orthographic
   variants. That observation drives the normalizer.
2. Run the same clip through local `faster-whisper small` int8 and time it on the
   actual demo laptop.
3. Verify `getUserMedia` works on a physical Android phone through
   `cloudflared`. If this fails, nothing else matters today.
4. Activate Model Studio (Singapore) if credentials exist.
5. **Do not** test Alibaba ASR for Urdu. Section 2 already answers it.
