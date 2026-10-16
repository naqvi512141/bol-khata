"""Create test fixture WAV from any audio file using app.ingest.audio.process_audio.

Usage:
    python scripts/make_fixture.py <input_audio_path>

Writes a 16 kHz mono s16le WAV to server/tests/fixtures/sample_ur.wav.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure server/ is on sys.path so 'app' package is importable.
_server_dir = Path(__file__).resolve().parent.parent / "server"
sys.path.insert(0, str(_server_dir))

from app.ingest.audio import process_audio  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/make_fixture.py <input_audio_path>", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1]).resolve()
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    raw_bytes = input_path.read_bytes()
    result = process_audio(raw_bytes)

    output_dir = _server_dir / "tests" / "fixtures"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "sample_ur.wav"
    output_path.write_bytes(result.wav_bytes)

    duration_s = result.duration_ms / 1000.0
    print(f"Output: {output_path}")
    print(f"Duration: {result.duration_ms} ms ({duration_s:.2f} s)")
    print(f"Size: {len(result.wav_bytes)} bytes")


if __name__ == "__main__":
    main()
