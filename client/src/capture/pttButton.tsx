import React, { useState, useRef, useEffect, useCallback } from 'react';
import { PushToTalkController, type RecordedAudio, type RecorderState } from './recorder';

interface PttButtonProps {
  onAudioCaptured: (audio: RecordedAudio) => void;
  disabled?: boolean;
}

export function PttButton({ onAudioCaptured, disabled }: PttButtonProps) {
  const [recState, setRecState] = useState<RecorderState>('idle');
  const [rms, setRms] = useState(0);
  const [duration, setDuration] = useState(0);
  const [tooShortWarning, setTooShortWarning] = useState(false);
  const controllerRef = useRef<PushToTalkController | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    controllerRef.current = new PushToTalkController({
      onStateChange: (state) => setRecState(state),
      onRmsUpdate: (val) => setRms(val),
      onError: (err) => console.error('Audio capture error:', err),
    });
  }, []);

  const handleStart = useCallback(async (e: React.SyntheticEvent) => {
    e.preventDefault();
    if (disabled || recState === 'recording' || recState === 'requesting') return;
    setTooShortWarning(false);
    setDuration(0);
    const startTs = Date.now();
    timerRef.current = window.setInterval(() => {
      setDuration(Math.floor((Date.now() - startTs) / 100) / 10);
    }, 100);

    if (controllerRef.current) {
      await controllerRef.current.start();
    }
  }, [disabled, recState]);

  const handleStop = useCallback(async (e: React.SyntheticEvent) => {
    e.preventDefault();
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (controllerRef.current && (recState === 'recording' || recState === 'requesting')) {
      const res = await controllerRef.current.stop();
      if (!res) {
        setTooShortWarning(true);
        setTimeout(() => setTooShortWarning(false), 2500);
      } else {
        onAudioCaptured(res);
      }
    }
  }, [recState, onAudioCaptured]);

  const isRecording = recState === 'recording';
  const rmsScale = Math.min(1.5, 1 + rms * 3);

  return (
    <div className="flex flex-col items-center justify-center gap-2 select-none">
      {tooShortWarning && (
        <div className="text-xs bg-amber-900/90 text-amber-200 px-3 py-1 rounded-full animate-bounce">
          آواز بہت مختصر ہے (کم از کم 0.7 سیکنڈ)
        </div>
      )}

      <div className="relative flex items-center justify-center">
        {isRecording && (
          <div
            className="absolute inset-0 rounded-full bg-red-600/40 animate-ping pointer-events-none"
            style={{ transform: `scale(${rmsScale})` }}
          />
        )}
        <button
          type="button"
          disabled={disabled}
          onMouseDown={handleStart}
          onMouseUp={handleStop}
          onMouseLeave={handleStop}
          onTouchStart={handleStart}
          onTouchEnd={handleStop}
          onTouchCancel={handleStop}
          className={`relative z-10 w-24 h-24 rounded-full flex flex-col items-center justify-center font-nastaliq shadow-2xl transition-all duration-150 active:scale-95 ${
            isRecording
              ? 'bg-red-600 text-white shadow-red-500/50 ring-4 ring-red-400'
              : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-700/50 ring-2 ring-emerald-400/40'
          } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
          aria-label="پش ٹو ٹاک بٹن"
        >
          <svg
            className={`w-8 h-8 mb-0.5 ${isRecording ? 'animate-pulse' : ''}`}
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
          <span className="text-xs font-semibold leading-none">
            {isRecording ? `${duration.toFixed(1)}s` : 'بولیں'}
          </span>
        </button>
      </div>

      <p className="text-xs text-gray-400 font-nastaliq text-center">
        {isRecording ? 'چھوڑنے پر کھاتہ بن جائے گا...' : 'دبا کر رکھیں اور بولیں'}
      </p>
    </div>
  );
}
