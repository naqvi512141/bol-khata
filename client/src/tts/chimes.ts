/**
 * Procedural Web Audio API chimes — zero-network, instantaneous, offline audio feedback.
 * Docs: docs/03-build-plan.md Phase 7: "Chime immediately; full spoken readback only when queue is empty."
 */

export type ChimeType = 'success' | 'review' | 'error';

class ChimePlayer {
  private ctx: AudioContext | null = null;

  private getContext(): AudioContext | null {
    if (typeof window === 'undefined') return null;
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {});
    }
    return this.ctx;
  }

  public play(type: ChimeType): void {
    const ctx = this.getContext();
    if (!ctx) return;

    try {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);

      if (type === 'success') {
        // High confidence commit: Pleasant rising two-tone chime (523 Hz -> 659 Hz)
        osc.type = 'sine';
        osc.frequency.setValueAtTime(523.25, now); // C5
        osc.frequency.setValueAtTime(659.25, now + 0.12); // E5

        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(0.25, now + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

        osc.start(now);
        osc.stop(now + 0.35);
      } else if (type === 'review') {
        // Needs review: Two warm mid-range pulses (440 Hz)
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(440, now); // A4

        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(0.2, now + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.02, now + 0.1);
        gain.gain.linearRampToValueAtTime(0.2, now + 0.14);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);

        osc.start(now);
        osc.stop(now + 0.3);
      } else if (type === 'error') {
        // Warning / Rejected: Descending tone (330 Hz -> 220 Hz)
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(329.63, now); // E4
        osc.frequency.exponentialRampToValueAtTime(220, now + 0.25); // A3

        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(0.18, now + 0.03);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.28);

        osc.start(now);
        osc.stop(now + 0.28);
      }
    } catch {
      // Audio playback might be prevented by browser auto-play policy before gesture
    }
  }
}

export const chimePlayer = new ChimePlayer();

