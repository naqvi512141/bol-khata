/**
 * Push-to-talk audio recorder hook with AudioContext metering.
 * Docs: docs/03-build-plan.md Phase 7.
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { getSupportedMimeType, computeRmsAndClipping } from './audioUtils';

export interface RecordedAudioResult {
  blob: Blob;
  duration_ms: number;
  peak_rms: number;
  clip_ratio: number;
  codec: string;
}

export function useAudioRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0); // 0 to 1 for visualizer
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(0);
  const animationFrameRef = useRef<number | null>(null);
  const peakRmsRef = useRef<number>(0);
  const clipSamplesRef = useRef<number>(0);
  const totalSamplesRef = useRef<number>(0);

  const cleanupAudioNodes = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    analyserRef.current = null;
    mediaRecorderRef.current = null;
    setAudioLevel(0);
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    chunksRef.current = [];
    peakRmsRef.current = 0;
    clipSamplesRef.current = 0;
    totalSamplesRef.current = 0;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          noiseSuppression: true,
          echoCancellation: true,
        },
      });
      streamRef.current = stream;

      const mimeType = getSupportedMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      // Set up AudioContext for live metering and clipping detection
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtx();
      audioContextRef.current = audioCtx;
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const dataArray = new Float32Array(analyser.fftSize);

      const updateMeter = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getFloatTimeDomainData(dataArray);
        const { rms, clipRatio } = computeRmsAndClipping(dataArray);
        if (rms > peakRmsRef.current) peakRmsRef.current = rms;
        if (clipRatio > 0) clipSamplesRef.current += 1;
        totalSamplesRef.current += 1;

        setAudioLevel(Math.min(1, rms * 4)); // Scale for UI responsiveness
        animationFrameRef.current = requestAnimationFrame(updateMeter);
      };

      recorder.start(100);
      startTimeRef.current = Date.now();
      setIsRecording(true);
      updateMeter();
    } catch (err) {
      cleanupAudioNodes();
      setIsRecording(false);
      setError(err instanceof Error ? err.message : 'مائیکروفون تک رسائی نہیں ہو سکی');
    }
  }, [cleanupAudioNodes]);

  const stopRecording = useCallback((): Promise<RecordedAudioResult | null> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state === 'inactive') {
        cleanupAudioNodes();
        setIsRecording(false);
        resolve(null);
        return;
      }

      recorder.onstop = () => {
        const duration_ms = Math.max(0, Date.now() - startTimeRef.current);
        const mimeType = recorder.mimeType || 'audio/webm';
        const blob = new Blob(chunksRef.current, { type: mimeType });

        const clipRatio =
          totalSamplesRef.current > 0
            ? clipSamplesRef.current / totalSamplesRef.current
            : 0;

        cleanupAudioNodes();
        setIsRecording(false);

        // Validation per docs/03-build-plan.md:
        if (duration_ms < 700) {
          setError('بہت مختصر آواز (کم از کم 1 سیکنڈ)');
          resolve(null);
          return;
        }

        resolve({
          blob,
          duration_ms,
          peak_rms: Number(peakRmsRef.current.toFixed(4)),
          clip_ratio: Number(clipRatio.toFixed(4)),
          codec: mimeType,
        });
      };

      try {
        recorder.stop();
      } catch {
        cleanupAudioNodes();
        setIsRecording(false);
        resolve(null);
      }
    });
  }, [cleanupAudioNodes]);

  useEffect(() => {
    return () => {
      cleanupAudioNodes();
    };
  }, [cleanupAudioNodes]);

  return {
    isRecording,
    audioLevel,
    error,
    startRecording,
    stopRecording,
  };
}

