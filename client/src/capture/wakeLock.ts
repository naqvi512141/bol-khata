/**
 * Screen Wake Lock API helper.
 * Prevents mobile screens from sleeping during recording or active interaction.
 */

export class ScreenWakeLockController {
  private _wakeLock: WakeLockSentinel | null = null;
  private _isSupported: boolean;

  constructor() {
    this._isSupported = typeof navigator !== 'undefined' && 'wakeLock' in navigator;
  }

  get isSupported(): boolean {
    return this._isSupported;
  }

  async acquire(): Promise<boolean> {
    if (!this._isSupported) return false;
    try {
      this._wakeLock = await navigator.wakeLock.request('screen');
      this._wakeLock.addEventListener('release', () => {
        this._wakeLock = null;
      });
      return true;
    } catch {
      this._wakeLock = null;
      return false;
    }
  }

  async release(): Promise<void> {
    if (this._wakeLock) {
      try {
        await this._wakeLock.release();
      } catch {
        // Ignore release errors
      } finally {
        this._wakeLock = null;
      }
    }
  }
}
