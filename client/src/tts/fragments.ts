/**
 * TTS fragment bank loader and concatenator with 20 ms crossfade.
 */

const CROSSFADE_SEC = 0.02; // 20 ms crossfade

class TTSBank {
  private _ctx: AudioContext | null = null;
  private _bufferCache = new Map<string, AudioBuffer>();

  private _getCtx(): AudioContext {
    if (!this._ctx || this._ctx.state === 'closed') {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this._ctx = new AudioCtx();
    }
    return this._ctx;
  }

  async loadFragment(name: string): Promise<AudioBuffer | null> {
    if (this._bufferCache.has(name)) {
      return this._bufferCache.get(name)!;
    }

    try {
      const res = await fetch(`/tts/${name}.mp3`);
      if (!res.ok) return null;
      const arrayBuf = await res.arrayBuffer();
      const audioBuf = await this._getCtx().decodeAudioData(arrayBuf);
      this._bufferCache.set(name, audioBuf);
      return audioBuf;
    } catch {
      return null;
    }
  }

  concatenateWithCrossfade(buffers: AudioBuffer[]): AudioBuffer | null {
    if (buffers.length === 0) return null;
    if (buffers.length === 1) return buffers[0];

    const ctx = this._getCtx();
    const sampleRate = buffers[0].sampleRate;
    const xfadeSamples = Math.floor(sampleRate * CROSSFADE_SEC);

    let totalSamples = buffers[0].length;
    for (let i = 1; i < buffers.length; i++) {
      totalSamples += buffers[i].length - xfadeSamples;
    }

    const outBuf = ctx.createBuffer(1, Math.max(1, totalSamples), sampleRate);
    const outData = outBuf.getChannelData(0);

    let writeOffset = 0;
    for (let bIdx = 0; bIdx < buffers.length; bIdx++) {
      const curData = buffers[bIdx].getChannelData(0);
      const isFirst = bIdx === 0;

      for (let i = 0; i < curData.length; i++) {
        if (!isFirst && i < xfadeSamples) {
          // Crossfade region: fade in current, fade out previous
          const t = i / xfadeSamples;
          outData[writeOffset + i] = outData[writeOffset + i] * (1 - t) + curData[i] * t;
        } else {
          outData[writeOffset + i] = curData[i];
        }
      }
      writeOffset += curData.length - (bIdx < buffers.length - 1 ? xfadeSamples : 0);
    }

    return outBuf;
  }

  async playSpeech(text: string, fragmentNames: string[]): Promise<void> {
    const loaded: AudioBuffer[] = [];
    for (const name of fragmentNames) {
      const buf = await this.loadFragment(name);
      if (buf) loaded.push(buf);
    }

    if (loaded.length > 0 && loaded.length === fragmentNames.length) {
      const finalBuf = this.concatenateWithCrossfade(loaded);
      if (finalBuf) {
        const ctx = this._getCtx();
        const source = ctx.createBufferSource();
        source.buffer = finalBuf;
        source.connect(ctx.destination);
        source.start();
        return;
      }
    }

    // Fallback: Browser Web Speech API with Urdu voice if available
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'ur-PK';
      window.speechSynthesis.speak(utterance);
    }
  }
}

export const ttsBank = new TTSBank();
