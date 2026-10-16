/**
 * Spoken readback queue — concatenates audio fragments with 20ms crossfade.
 * Rule: Full readback only when queue is empty.
 */

import { chimePlayer } from './chimes';
import type { ParsedDraft } from '../types';

export class ReadbackService {
  private isSpeaking: boolean = false;

  public async announceDraft(draft: ParsedDraft, isQueueEmpty: boolean = true): Promise<void> {
    // If not empty, chime only
    if (!isQueueEmpty) {
      if (draft.confidence >= 0.85 && draft.validation.passed) {
        chimePlayer.play('success');
      } else {
        chimePlayer.play('review');
      }
      return;
    }

    // Play chime first
    if (draft.confidence >= 0.85 && draft.validation.passed) {
      chimePlayer.play('success');
    } else {
      chimePlayer.play('review');
    }

    // Check if browser Web Speech API or audio fragments are available
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      this.speakText(this.formatDraftForSpeech(draft));
    }
  }

  private formatDraftForSpeech(draft: ParsedDraft): string {
    const cust = draft.customer.raw_name || 'نقد فروخت';
    const amount = draft.computed_total;
    return `${cust}، کل رقم ${amount} روپے۔`;
  }

  private speakText(text: string): void {
    if (this.isSpeaking) {
      window.speechSynthesis.cancel();
    }
    this.isSpeaking = true;

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'ur-PK';
    utterance.rate = 1.0;

    utterance.onend = () => {
      this.isSpeaking = false;
    };
    utterance.onerror = () => {
      this.isSpeaking = false;
    };

    window.speechSynthesis.speak(utterance);
  }
}

export const readbackService = new ReadbackService();

