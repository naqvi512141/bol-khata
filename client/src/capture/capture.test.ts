import { generateUlid } from './ulid.ts';
import { selectSupportedCodec, CODEC_CANDIDATES } from './codec.ts';
import { computeRms, computeClipRatio, StreamAudioAnalyzer } from './audioAnalysis.ts';
import { PushToTalkController, type RecordedAudio } from './recorder.ts';

function assertTrue(condition: boolean, message: string): void {
  if (!condition) throw new Error(`Assertion failed: ${message}`);
}

function assertEqual<T>(actual: T, expected: T, message?: string): void {
  if (actual !== expected) {
    throw new Error(`Assertion failed: ${message ?? ''} (expected ${expected}, got ${actual})`);
  }
}

function testUlid() {
  const id1 = generateUlid(1000);
  const id2 = generateUlid(2000);
  assertEqual(id1.length, 26, 'ULID must be exactly 26 characters');
  assertEqual(id2.length, 26, 'ULID must be exactly 26 characters');
  assertTrue(/^[0-9A-Z]{26}$/.test(id1), 'ULID must only use Crockford Base32 chars');
  assertTrue(id1 < id2, 'ULID must be lexicographically sortable by timestamp');
  console.log('✓ ULID tests passed');
}

function testCodecSelection() {
  const c1 = selectSupportedCodec(CODEC_CANDIDATES, (mime) => mime === 'audio/webm;codecs=opus');
  assertEqual(c1, 'audio/webm;codecs=opus');

  const c2 = selectSupportedCodec(CODEC_CANDIDATES, (mime) => mime === 'audio/mp4');
  assertEqual(c2, 'audio/mp4');

  const c3 = selectSupportedCodec(CODEC_CANDIDATES, () => false);
  assertEqual(c3, '');

  console.log('✓ Codec fallback ladder tests passed');
}

function testAudioAnalysis() {
  const silence = new Float32Array(100).fill(0);
  assertEqual(computeRms(silence), 0);
  assertEqual(computeClipRatio(silence), 0);

  const halfAmp = new Float32Array(100).fill(0.5);
  assertEqual(computeRms(halfAmp), 0.5);
  assertEqual(computeClipRatio(halfAmp), 0);

  const clipped = new Float32Array([0.1, 0.5, 0.99, 1.0]);
  assertEqual(computeClipRatio(clipped, 0.99), 0.5);

  const analyzer = new StreamAudioAnalyzer(0.02, 0.99);
  const f1 = analyzer.processFrame(new Float32Array([0.01, 0.01]));
  assertEqual(f1.isSpeech, false);

  const f2 = analyzer.processFrame(new Float32Array([0.1, 0.2]));
  assertEqual(f2.isSpeech, true);

  const stats = analyzer.getStats();
  assertTrue(stats.peakRms > 0, 'peak RMS must be > 0');
  assertEqual(stats.speechFramesRatio, 0.5);

  console.log('✓ Audio analysis & VAD tests passed');
}

async function testRecorderMock() {
  const mockTrack = { stop: () => {} };
  const mockStream = { getTracks: () => [mockTrack] } as unknown as MediaStream;

  class MockRecorder {
    state = 'inactive';
    ondataavailable: ((e: { data: Blob }) => void) | null = null;
    onstop: (() => void) | null = null;

    start() {
      this.state = 'recording';
      setTimeout(() => {
        this.ondataavailable?.({ data: new Blob(['fake-audio-chunk'], { type: 'audio/webm' }) });
      }, 5);
    }

    stop() {
      this.state = 'inactive';
      setTimeout(() => {
        this.onstop?.();
      }, 5);
    }
  }

  // Test 1: Duration too short (< 700 ms) rejected
  const shortController = new PushToTalkController({
    minDurationMs: 700,
    streamProvider: async () => mockStream,
    mediaRecorderFactory: () => new MockRecorder() as unknown as MediaRecorder,
  });

  await shortController.start();
  assertEqual(shortController.state, 'recording');
  const shortResult = await shortController.stop();
  assertEqual(shortResult, null, 'Clip shorter than minDurationMs must be rejected');

  // Test 2: Valid duration returns RecordedAudio with ULID
  const validController = new PushToTalkController({
    minDurationMs: 10,
    streamProvider: async () => mockStream,
    mediaRecorderFactory: () => new MockRecorder() as unknown as MediaRecorder,
  });

  await validController.start();
  await new Promise((r) => setTimeout(r, 20));
  const validResult: RecordedAudio | null = await validController.stop();

  assertTrue(validResult !== null, 'Valid clip must return RecordedAudio');
  if (validResult) {
    assertEqual(validResult.jobId.length, 26, 'jobId must be a 26-char ULID');
    assertTrue(validResult.durationMs >= 10, 'durationMs must be tracked');
    assertTrue(validResult.blob.size > 0, 'audio blob must be captured');
  }

  console.log('✓ Recorder mock & state transition tests passed');
}

export async function runAllTests(): Promise<void> {
  testUlid();
  testCodecSelection();
  testAudioAnalysis();
  await testRecorderMock();
  console.log('\nAll capture unit tests passed successfully!');
}

runAllTests().catch((err: unknown) => {
  console.error('Test failed:', err);
});
