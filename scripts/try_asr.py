#!/usr/bin/env python3
"""Manual ASR diagnostic — not part of the test suite.

Usage:
    cd server
    python -m scripts.try_asr path/to/audio.wav
    # or from project root:
    python scripts/try_asr.py path/to/audio.ogg

Runs each available engine (groq, local) twice on the given audio file:
  1. No bias prompt
  2. With the catalogue/customer bias prompt

Prints raw transcript, per-segment avg_logprob, derived confidence, and
elapsed time.  If an engine fails, the error is printed and the next engine
is tried — the script never aborts early.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Ensure the server package is importable regardless of cwd
_SCRIPT_DIR = Path(__file__).resolve().parent
_SERVER_DIR = _SCRIPT_DIR.parent / "server"
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

# Load .env from project root so GROQ_API_KEY etc. are available
_PROJECT_ROOT = _SCRIPT_DIR.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    os.environ.setdefault("ENV_FILE", str(_ENV_FILE))
    # Lightweight dotenv-style load (pydantic-settings reads it too, but we
    # want the key available before we instantiate engines).
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        os.environ.setdefault(key, val)


from app.asr.bias import build_bias_prompt  # noqa: E402
from app.asr.groq_whisper import GroqASRError, GroqWhisperEngine  # noqa: E402
from app.ingest.audio import process_audio  # noqa: E402
from app.schemas import RawASRPayload  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEPARATOR = "─" * 72


def _print_result(payload: RawASRPayload) -> None:
    """Pretty-print a single ASR result."""
    print(f"  engine        : {payload.engine}")
    print(f"  model         : {payload.model_name}")
    print(f"  raw_text      : {payload.raw_text}")
    print(f"  asr_confidence: {payload.asr_confidence:.4f}")
    print(f"  processing_ms : {payload.processing_ms}")
    if payload.segments:
        for i, seg in enumerate(payload.segments):
            print(
                f"    seg[{i}] avg_logprob={seg.avg_logprob:.4f}  "
                f"no_speech={seg.no_speech_prob:.4f}  "
                f"[{seg.start:.2f}–{seg.end:.2f}]  "
                f'"{seg.text}"'
            )
    else:
        print("    (no segments)")


def _try_engine(
    name: str,
    run_fn: object,
    audio: object,
    bias_prompt: str,
) -> None:
    """Run an engine twice (no-bias, with-bias) and print results or errors."""
    from app.ingest.audio import IngestedAudio  # local import to keep types right

    assert callable(run_fn)
    assert isinstance(audio, IngestedAudio)

    for label, prompt in [("no bias prompt", ""), ("with bias prompt", bias_prompt)]:
        print(f"\n{SEPARATOR}")
        print(f"  {name}  |  {label}")
        print(SEPARATOR)
        try:
            payload = run_fn(
                audio=audio,
                job_id=f"try_{name}",
                shop_id="demo",
                prompt=prompt,
            )
            _print_result(payload)
        except Exception as exc:
            print(f"  ✗ {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    # Windows consoles default to cp1252 which can't encode Urdu.
    # Force UTF-8 with replacement so the script never crashes on output.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    audio_path = Path(sys.argv[1])
    if not audio_path.exists():
        print(f"File not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    raw_bytes = audio_path.read_bytes()
    print(f"Input : {audio_path}  ({len(raw_bytes)} bytes)")

    # Ingest (resample to 16 kHz mono WAV)
    audio = process_audio(raw_bytes)
    print(f"After ingest: {audio.duration_ms} ms, clip_ratio={audio.clip_ratio:.4f}")

    bias_prompt = build_bias_prompt()
    print(f"Bias prompt ({len(bias_prompt)} chars):")
    # Print first 120 chars so the terminal doesn't flood with Urdu
    preview = bias_prompt[:120] + ("…" if len(bias_prompt) > 120 else "")
    print(f"  {preview}")

    # ── Groq engine ──────────────────────────────────────────────────────
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            groq = GroqWhisperEngine(api_key=groq_key)
            _try_engine("groq", groq.transcribe, audio, bias_prompt)
        except Exception as exc:
            print(f"\n  ✗ Groq init failed: {type(exc).__name__}: {exc}")
    else:
        print("\n  ⊘ Skipping Groq (GROQ_API_KEY not set)")

    # ── Local faster-whisper engine ───────────────────────────────────────
    try:
        from app.asr.local_whisper import LocalWhisperEngine

        local = LocalWhisperEngine(model_size="small", device="cpu", compute_type="int8")
        _try_engine("local", local.transcribe, audio, bias_prompt)
    except Exception as exc:
        print(f"\n  ✗ Local engine failed: {type(exc).__name__}: {exc}")

    print(f"\n{SEPARATOR}")
    print("Done.")


if __name__ == "__main__":
    main()
