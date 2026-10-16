/**
 * Push-to-talk button component with animated pulse and touch handlers.
 * AGENTS.md rule: Push-to-talk only. No always-on listening, no wake word.
 */

import { useRef } from 'react';

interface PushToTalkButtonProps {
  isRecording: boolean;
  audioLevel: number;
  disabled?: boolean;
  onStart: () => void;
  onStop: () => void;
}

export function PushToTalkButton({
  isRecording,
  audioLevel,
  disabled = false,
  onStart,
  onStop,
}: PushToTalkButtonProps) {
  const isPointerDownRef = useRef(false);

  const handlePointerDown = (e: React.PointerEvent) => {
    if (disabled || isRecording) return;
    e.preventDefault();
    isPointerDownRef.current = true;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    onStart();
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (!isPointerDownRef.current) return;
    e.preventDefault();
    isPointerDownRef.current = false;
    onStop();
  };

  const scale = isRecording ? 1 + Math.min(0.35, audioLevel * 0.4) : 1;

  return (
    <div className="flex flex-col items-center justify-center select-none py-4">
      <div className="relative flex items-center justify-center">
        {/* Animated outer ring during recording */}
        {isRecording && (
          <div
            className="absolute rounded-full bg-emerald-500/20 transition-all duration-75"
            style={{
              width: `${120 * scale}px`,
              height: `${120 * scale}px`,
            }}
          />
        )}

        {/* Main button */}
        <button
          type="button"
          disabled={disabled}
          onPointerDown={handlePointerDown}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          className={`relative z-10 w-24 h-24 rounded-full flex flex-col items-center justify-center shadow-xl transition-all active:scale-95 touch-none ${
            isRecording
              ? 'bg-red-600 shadow-red-500/40 text-white animate-pulse'
              : disabled
              ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
              : 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-500/30 text-white'
          }`}
          aria-label={isRecording ? 'بول رہے ہیں' : 'بولنے کے لیے دبا کر رکھیں'}
        >
          {/* Microphone SVG icon */}
          <svg
            className={`w-9 h-9 transition-transform ${isRecording ? 'scale-110' : ''}`}
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
        </button>
      </div>

      {/* Status instruction in Urdu */}
      <p className="mt-3 font-nastaliq text-sm text-gray-300 text-center">
        {isRecording ? (
          <span className="text-red-400 font-semibold animate-pulse">سن رہا ہے... بول کر چھوڑیں</span>
        ) : (
          <span>بولنے کے لیے دبا کر رکھیں</span>
        )}
      </p>
    </div>
  );
}

