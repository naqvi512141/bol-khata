import { generateUlid } from './ulid.ts';
import { selectSupportedCodec } from './codec.ts';
import { StreamAudioAnalyzer, type AudioStats } from './audioAnalysis.ts';
import { ScreenWakeLockController } from './wakeLock.ts';

export type RecorderState = 'idle' | 'requesting' | 'recording' | 'stopping' | 'error';

export interface RecordedAudio {
  jobId: string;
  blob: Blob;
  durationMs: number;
  peakRms: number;
  clipRatio: number;
  codec: string;
  capturedAt: string;
}

export interface RecorderOptions {
  minDurationMs?: number;
  maxDurationMs?: number;
  streamProvider?: () => Promise<MediaStream>;
  mediaRecorderFactory?: (stream: MediaStream, options?: MediaRecorderOptions) => MediaRecorder;
  audioContextFactory?: () => AudioContext;
  onStateChange?: (state: RecorderState) => void;
  onRmsUpdate?: (rms: number, peakRms: number, isSpeech: boolean) => void;
  onError?: (err: Error) => void;
}

export class PushToTalkController {
  private _state: RecorderState = 'idle';
  private _stream: MediaStream | null = null;
  private _recorder: MediaRecorder | null = null;
  private _ctx: AudioContext | null = null;
  private _node: AnalyserNode | null = null;
  private _analyzer = new StreamAudioAnalyzer();
  private _wakeLock = new ScreenWakeLockController();
  private _startTime = 0;
  private _chunks: Blob[] = [];
  private _activeCodec = '';
  private _animId: number | null = null;

  readonly minDurationMs: number;
  readonly maxDurationMs: number;
  private readonly _opts: RecorderOptions;

  constructor(options: RecorderOptions = {}) {
    this._opts = options;
    this.minDurationMs = options.minDurationMs ?? 700;
    this.maxDurationMs = options.maxDurationMs ?? 20000;
  }

  get state(): RecorderState {
    return this._state;
  }

  private _setState(state: RecorderState): void {
    this._state = state;
    this._opts.onStateChange?.(state);
  }

  async start(): Promise<void> {
    if (this._state !== 'idle') return;
    this._setState('requesting');
    this._chunks = [];
    this._analyzer.reset();

    try {
      this._stream = this._opts.streamProvider
        ? await this._opts.streamProvider()
        : await navigator.mediaDevices.getUserMedia({
            audio: { channelCount: 1, sampleRate: 16000, noiseSuppression: true, echoCancellation: false },
          });
      await this._wakeLock.acquire();

      this._activeCodec = selectSupportedCodec();
      const opts: MediaRecorderOptions = this._activeCodec ? { mimeType: this._activeCodec } : {};
      this._recorder = this._opts.mediaRecorderFactory
        ? this._opts.mediaRecorderFactory(this._stream, opts)
        : new MediaRecorder(this._stream, opts);

      this._recorder.ondataavailable = (e) => {
        if (e.data?.size > 0) this._chunks.push(e.data);
      };

      this._startAnalysis(this._stream);
      this._startTime = Date.now();
      this._recorder.start(100);
      this._setState('recording');
    } catch (err) {
      this._cleanup();
      this._setState('error');
      this._opts.onError?.(err instanceof Error ? err : new Error(String(err)));
    }
  }

  private _startAnalysis(stream: MediaStream): void {
    try {
      this._ctx = this._opts.audioContextFactory ? this._opts.audioContextFactory() : new AudioContext();
      const src = this._ctx.createMediaStreamSource(stream);
      this._node = this._ctx.createAnalyser();
      this._node.fftSize = 512;
      src.connect(this._node);

      const buf = new Float32Array(this._node.fftSize);
      const poll = () => {
        if (this._state !== 'recording' || !this._node) return;
        this._node.getFloatTimeDomainData(buf);
        const { rms, isSpeech } = this._analyzer.processFrame(buf);
        const stats = this._analyzer.getStats();
        this._opts.onRmsUpdate?.(rms, stats.peakRms, isSpeech);

        if (Date.now() - this._startTime >= this.maxDurationMs) {
          this.stop().catch(() => {});
          return;
        }
        this._animId = requestAnimationFrame(poll);
      };
      this._animId = requestAnimationFrame(poll);
    } catch {
      // Audio analysis failure shouldn't abort recording
    }
  }

  async stop(): Promise<RecordedAudio | null> {
    if (this._state !== 'recording' || !this._recorder) return null;
    this._setState('stopping');
    const stopTime = Date.now();
    const durationMs = stopTime - this._startTime;
    const capturedAt = new Date(stopTime).toISOString();
    // Rule: ULID generated at button release
    const jobId = generateUlid(stopTime);

    return new Promise<RecordedAudio | null>((resolve) => {
      if (!this._recorder) {
        this._cleanup();
        this._setState('idle');
        resolve(null);
        return;
      }

      this._recorder.onstop = () => {
        const mimeType = this._chunks[0]?.type || this._activeCodec || 'audio/webm';
        const blob = new Blob(this._chunks, { type: mimeType });
        const stats: AudioStats = this._analyzer.getStats();
        this._cleanup();
        this._setState('idle');

        if (durationMs < this.minDurationMs) {
          resolve(null); // Too short (< 700 ms)
          return;
        }

        resolve({
          jobId,
          blob,
          durationMs,
          peakRms: Number(stats.peakRms.toFixed(4)),
          clipRatio: Number(stats.clipRatio.toFixed(4)),
          codec: mimeType,
          capturedAt,
        });
      };

      try {
        this._recorder.stop();
      } catch {
        this._cleanup();
        this._setState('idle');
        resolve(null);
      }
    });
  }

  private _cleanup(): void {
    if (this._animId !== null) cancelAnimationFrame(this._animId);
    this._animId = null;
    if (this._stream) {
      this._stream.getTracks().forEach((t) => t.stop());
      this._stream = null;
    }
    if (this._ctx && this._ctx.state !== 'closed') {
      this._ctx.close().catch(() => {});
      this._ctx = null;
    }
    this._node = null;
    this._recorder = null;
    this._wakeLock.release().catch(() => {});
  }
}
