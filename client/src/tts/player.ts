import { playSuccessChime, playWarningChime, playErrorChime } from './chimes';
import { ttsBank } from './fragments';
import type { ParsedDraft } from '../types';

export class TTSPlayer {
  private _pendingReadback: ParsedDraft | null = null;

  playBandChime(band: 'high' | 'medium' | 'low'): void {
    if (band === 'high') {
      playSuccessChime();
    } else if (band === 'medium') {
      playWarningChime();
    } else {
      playErrorChime();
    }
  }

  queueReadback(draft: ParsedDraft): void {
    this._pendingReadback = draft;
  }

  onQueueEmpty(): void {
    if (!this._pendingReadback) return;
    const draft = this._pendingReadback;
    this._pendingReadback = null;

    // Build readback fragments and Urdu text
    const custName = draft.customer.raw_name ?? 'نقد';
    const total = draft.computed_total;
    const text = `${custName}، ${total} روپے`;

    // Try loading fragments if available, or fall back to speech synthesis
    const fragments = ['chime', `num_${total}`, 'rupees'];
    ttsBank.playSpeech(text, fragments).catch(() => {});
  }
}

export const ttsPlayer = new TTSPlayer();
