#!/usr/bin/env python3
"""Build static Urdu TTS fragment bank using edge-tts.

Docs: docs/03-build-plan.md Phase 8; docs/04-stack.md §4.
Voice: ur-PK-UzmaNeural
Destination: client/public/tts/

Generates:
- Cardinals 0-99
- Multipliers (sau, hazaar, lakh)
- Fractional quantifiers (aadha, paw, derh, dhai, sawa, saarhe, paun)
- Units (kilo, gram, litre, milli_litre, darjan, packet, botal, dabba, adad)
- Frame phrases (ka_hisaab, kul_raqam, rupay, udhaar, naqd, wasooli, baaqi)
- Three chimes (success, review, error)
- manifest.json indexing all fragments

Run offline once; the runtime application must never call edge-tts directly.
"""

from __future__ import annotations

import asyncio
import io
import json
import math
import struct
import sys
import wave
from pathlib import Path

# Paths
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _PROJECT_ROOT / "server" / "data"
_OUTPUT_DIR = _PROJECT_ROOT / "client" / "public" / "tts"
_CHIMES_DIR = _OUTPUT_DIR / "chimes"

VOICE = "ur-PK-UzmaNeural"


def generate_wav_chime(
    filename: Path,
    frequencies: list[tuple[float, float, float]],  # (freq_hz, start_s, duration_s)
    total_duration_s: float = 0.35,
    sample_rate: int = 22050,
) -> None:
    """Generate a clean procedural WAV chime using sine synthesis."""
    num_samples = int(total_duration_s * sample_rate)
    samples: list[float] = [0.0] * num_samples

    for freq, start_s, dur_s in frequencies:
        start_idx = int(start_s * sample_rate)
        dur_samples = int(dur_s * sample_rate)
        end_idx = min(num_samples, start_idx + dur_samples)

        for i in range(start_idx, end_idx):
            t = (i - start_idx) / sample_rate
            # Sine wave with exponential decay envelope
            decay = math.exp(-6.0 * (t / dur_s))
            val = math.sin(2.0 * math.pi * freq * t) * decay * 0.4
            samples[i] += val

    # Normalize and convert to 16-bit PCM
    max_val = max(abs(s) for s in samples) if samples else 1.0
    scale = 32000.0 / max(max_val, 1.0)
    pcm_data = bytearray()
    for s in samples:
        int_sample = max(-32767, min(32767, int(s * scale)))
        pcm_data.extend(struct.pack("<h", int_sample))

    filename.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(filename), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)


def build_chimes() -> dict[str, str]:
    """Build the three procedural chimes."""
    _CHIMES_DIR.mkdir(parents=True, exist_ok=True)
    chimes_map: dict[str, str] = {}

    # 1. Success chime: Rising C5 (523.25 Hz) -> E5 (659.25 Hz)
    success_file = _CHIMES_DIR / "chime_success.wav"
    generate_wav_chime(
        success_file,
        [(523.25, 0.0, 0.2), (659.25, 0.12, 0.25)],
        total_duration_s=0.38,
    )
    chimes_map["chime_success"] = "chimes/chime_success.wav"

    # 2. Review chime: Double tone A4 (440 Hz)
    review_file = _CHIMES_DIR / "chime_review.wav"
    generate_wav_chime(
        review_file,
        [(440.0, 0.0, 0.12), (440.0, 0.15, 0.18)],
        total_duration_s=0.35,
    )
    chimes_map["chime_review"] = "chimes/chime_review.wav"

    # 3. Error chime: Descending tone E4 (329.63 Hz) -> A3 (220 Hz)
    error_file = _CHIMES_DIR / "chime_error.wav"
    generate_wav_chime(
        error_file,
        [(329.63, 0.0, 0.15), (220.0, 0.12, 0.22)],
        total_duration_s=0.35,
    )
    chimes_map["chime_error"] = "chimes/chime_error.wav"

    return chimes_map


async def synthesize_fragment(
    edge_tts_mod: object,
    text: str,
    output_path: Path,
) -> bool:
    """Synthesize a single text phrase to MP3 using edge-tts."""
    try:
        communicate_cls = getattr(edge_tts_mod, "Communicate")
        communicate = communicate_cls(text=text, voice=VOICE)
        await communicate.save(str(output_path))
        return True
    except Exception as exc:
        print(f"  ✗ Failed for '{text}': {exc}", file=sys.stderr)
        return False


async def main() -> None:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Building Bol Khata TTS fragment bank...")

    # Build procedural chimes
    chimes = build_chimes()
    print("  ✓ Procedural chimes built (success, review, error)")

    manifest: dict[str, dict[str, str]] = {
        "voice": {"name": VOICE, "lang": "ur-PK"},
        "chimes": chimes,
        "fragments": {},
    }

    # Collect vocabulary items
    items_to_generate: list[tuple[str, str, str]] = []  # (category, key, text)

    # 1. Numerals from urdu_numerals.json
    numerals_path = _DATA_DIR / "urdu_numerals.json"
    if numerals_path.exists():
        raw_num = json.loads(numerals_path.read_text(encoding="utf-8"))
        cardinals: dict[str, int] = raw_num.get("cardinals", {})
        for word, val in cardinals.items():
            items_to_generate.append(("cardinals", f"num_{val}", word))
        multipliers: dict[str, int] = raw_num.get("multipliers", {})
        for word, val in multipliers.items():
            items_to_generate.append(("multipliers", f"mult_{val}", word))

    # 2. Fractional quantifiers
    fractions = [
        ("frac_aadha", "آدھا"),
        ("frac_paw", "پاؤ"),
        ("frac_derh", "ڈیڑھ"),
        ("frac_dhai", "ڈھائی"),
        ("frac_sawa", "سوا"),
        ("frac_saarhe", "ساڑھے"),
        ("frac_paun", "پونے"),
    ]
    for key, text in fractions:
        items_to_generate.append(("fractions", key, text))

    # 3. Units
    units = [
        ("unit_kg", "کلو"),
        ("unit_g", "گرام"),
        ("unit_l", "لیٹر"),
        ("unit_ml", "ملی لیٹر"),
        ("unit_dozen", "درجن"),
        ("unit_packet", "پیکٹ"),
        ("unit_bottle", "بوتل"),
        ("unit_box", "ڈبہ"),
        ("unit_piece", "عدد"),
    ]
    for key, text in units:
        items_to_generate.append(("units", key, text))

    # 4. Frame phrases
    frame_phrases = [
        ("frame_ka_hisaab", "کا حساب"),
        ("frame_kul_raqam", "کل رقم"),
        ("frame_rupay", "روپے"),
        ("frame_udhaar", "ادھار"),
        ("frame_naqd", "نقد"),
        ("frame_wasooli", "وصولی"),
        ("frame_baaqi", "باقی"),
    ]
    for key, text in frame_phrases:
        items_to_generate.append(("frames", key, text))

    # Check edge-tts availability
    try:
        import edge_tts  # type: ignore[import-not-found]
        has_edge_tts = True
    except ImportError:
        has_edge_tts = False

    if not has_edge_tts:
        print("\n  ⊘ edge-tts package is not installed.")
        print("    To generate live speech MP3s from Microsoft's ur-PK-UzmaNeural voice:")
        print("      pip install edge-tts --break-system-packages")
        print("      python scripts/build_tts_bank.py")
        print("    Proceeding with chimes and fragment manifest...")

        for cat, key, text in items_to_generate:
            rel_path = f"{cat}/{key}.mp3"
            manifest["fragments"][key] = {
                "category": cat,
                "text": text,
                "path": rel_path,
                "status": "pending_edge_tts",
            }
    else:
        print(f"\n  Synthesizing {len(items_to_generate)} Urdu speech fragments via {VOICE}...")
        for cat, key, text in items_to_generate:
            cat_dir = _OUTPUT_DIR / cat
            cat_dir.mkdir(parents=True, exist_ok=True)
            out_file = cat_dir / f"{key}.mp3"
            rel_path = f"{cat}/{key}.mp3"

            success = await synthesize_fragment(edge_tts, text, out_file)
            manifest["fragments"][key] = {
                "category": cat,
                "text": text,
                "path": rel_path,
                "status": "generated" if success else "failed",
            }

    # Write manifest
    manifest_path = _OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ Fragment bank manifest saved to {manifest_path}")


if __name__ == "__main__":
    asyncio.run(main())

