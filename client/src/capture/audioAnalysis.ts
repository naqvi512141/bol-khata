/**
 * Audio analysis: RMS calculation, peak RMS, clip ratio detection, and VAD thresholding.
 * Pure functions and accumulator class, fully unit-testable with synthetic Float32Array.
 */

export interface AudioStats {
  peakRms: number;
  avgRms: number;
  clipRatio: number;
  speechFramesRatio: number;
}

export function computeRms(samples: Float32Array): number {
  if (samples.length === 0) return 0.0;
  let sumSq = 0;
  for (let i = 0; i < samples.length; i++) {
    const s = samples[i];
    sumSq += s * s;
  }
  return Math.sqrt(sumSq / samples.length);
}

export function computeClipRatio(samples: Float32Array, threshold = 0.99): number {
  if (samples.length === 0) return 0.0;
  let clipCount = 0;
  for (let i = 0; i < samples.length; i++) {
    if (Math.abs(samples[i]) >= threshold) {
      clipCount++;
    }
  }
  return clipCount / samples.length;
}

export class StreamAudioAnalyzer {
  private _peakRms = 0.0;
  private _sumRms = 0.0;
  private _frameCount = 0;
  private _clipCount = 0;
  private _totalSamples = 0;
  private _speechFrameCount = 0;
  private readonly _vadThreshold: number;
  private readonly _clipThreshold: number;

  constructor(vadThreshold = 0.02, clipThreshold = 0.99) {
    this._vadThreshold = vadThreshold;
    this._clipThreshold = clipThreshold;
  }

  processFrame(samples: Float32Array): { rms: number; isSpeech: boolean } {
    if (samples.length === 0) {
      return { rms: 0, isSpeech: false };
    }

    const rms = computeRms(samples);
    if (rms > this._peakRms) {
      this._peakRms = rms;
    }

    this._sumRms += rms;
    this._frameCount++;

    const isSpeech = rms >= this._vadThreshold;
    if (isSpeech) {
      this._speechFrameCount++;
    }

    for (let i = 0; i < samples.length; i++) {
      if (Math.abs(samples[i]) >= this._clipThreshold) {
        this._clipCount++;
      }
    }
    this._totalSamples += samples.length;

    return { rms, isSpeech };
  }

  getStats(): AudioStats {
    return {
      peakRms: Math.min(1.0, this._peakRms),
      avgRms: this._frameCount > 0 ? this._sumRms / this._frameCount : 0.0,
      clipRatio: this._totalSamples > 0 ? this._clipCount / this._totalSamples : 0.0,
      speechFramesRatio: this._frameCount > 0 ? this._speechFrameCount / this._frameCount : 0.0,
    };
  }

  reset(): void {
    this._peakRms = 0.0;
    this._sumRms = 0.0;
    this._frameCount = 0;
    this._clipCount = 0;
    this._totalSamples = 0;
    this._speechFrameCount = 0;
  }
}
