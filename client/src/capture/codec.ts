/**
 * Codec fallback ladder for audio recording.
 * Selects the best supported mime type for MediaRecorder.
 */

export const CODEC_CANDIDATES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg;codecs=opus',
  'audio/mp4',
] as const;

export type MimeTypeChecker = (type: string) => boolean;

export function selectSupportedCodec(
  candidates: readonly string[] = CODEC_CANDIDATES,
  checker?: MimeTypeChecker
): string {
  const isSupported =
    checker ??
    ((mime: string) => {
      if (typeof MediaRecorder === 'undefined' || !MediaRecorder.isTypeSupported) {
        return false;
      }
      return MediaRecorder.isTypeSupported(mime);
    });

  for (const candidate of candidates) {
    if (isSupported(candidate)) {
      return candidate;
    }
  }

  return ''; // Browser default
}
