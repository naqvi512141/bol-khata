/**
 * Audio capture utilities: codec fallback ladder, RMS VAD, clip ratio.
 * Docs: docs/03-build-plan.md Phase 7.
 */

export const CODEC_LADDER = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/mp4',
  'audio/ogg;codecs=opus',
  'audio/wav',
];

export function getSupportedMimeType(): string {
  if (typeof MediaRecorder === 'undefined') {
    return 'audio/webm';
  }
  for (const mime of CODEC_LADDER) {
    if (MediaRecorder.isTypeSupported(mime)) {
      return mime;
    }
  }
  return '';
}

export function computeRmsAndClipping(buffer: Float32Array): { rms: number; clipRatio: number } {
  if (buffer.length === 0) {
    return { rms: 0, clipRatio: 0 };
  }

  let sumSquares = 0;
  let clippedCount = 0;
  const clipThreshold = 0.98;

  for (let i = 0; i < buffer.length; i++) {
    const val = buffer[i];
    sumSquares += val * val;
    if (Math.abs(val) >= clipThreshold) {
      clippedCount++;
    }
  }

  const rms = Math.sqrt(sumSquares / buffer.length);
  const clipRatio = clippedCount / buffer.length;
  return { rms, clipRatio };
}

