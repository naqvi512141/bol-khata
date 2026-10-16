import { useState, useEffect, useRef, useCallback } from 'react';
import { db } from './db';
import type { CaptureJob, LedgerEvent, ParsedDraft } from './types';
import type { RecordedAudio } from './capture/recorder';
import { JobQueueManager } from './queue/jobQueue';
import { DraftManager, type DraftState } from './draft/draftManager';
import { evaluateConfidenceBand } from './confirm/confidenceBands';
import { commitDraftToLedger, commitManualOfflineSale } from './ledger/events';
import { ttsPlayer } from './tts/player';
import { generateUlid } from './capture/ulid';

const SHOP_ID = 'demo_shop_01';

export function useBolKhata() {
  const [deviceId, setDeviceId] = useState<string>('dev_001');
  const [events, setEvents] = useState<LedgerEvent[]>([]);
  const [heldDrafts, setHeldDrafts] = useState<ParsedDraft[]>([]);
  const [draftState, setDraftState] = useState<DraftState>({ draft: null, expiresAt: null, secondsRemaining: 0 });
  const [undoDraft, setUndoDraft] = useState<ParsedDraft | null>(null);
  const [queueStats, setQueueStats] = useState({ inFlight: 0, queued: 0 });
  const [isTrayOpen, setIsTrayOpen] = useState(false);
  const [degradedJob, setDegradedJob] = useState<CaptureJob | null>(null);

  const queueRef = useRef<JobQueueManager | null>(null);
  const draftMgrRef = useRef<DraftManager | null>(null);
  const activeUndoDraftRef = useRef<ParsedDraft | null>(null);

  const loadEvents = useCallback(async () => {
    const all = await db.events.orderBy('created_at').toArray();
    setEvents(all);
  }, []);

  const executeCommit = useCallback(
    async (draft: ParsedDraft) => {
      const dev = deviceId || 'dev_001';
      await commitDraftToLedger(draft, dev);
      ttsPlayer.queueReadback(draft);
      if (queueStats.inFlight === 0 && queueStats.queued === 0) {
        ttsPlayer.onQueueEmpty();
      }
      draftMgrRef.current?.commitDone();
      setUndoDraft(null);
      activeUndoDraftRef.current = null;
      loadEvents();
    },
    [deviceId, loadEvents, queueStats]
  );

  const handleDraftEvaluated = useCallback((draft: ParsedDraft) => {
    const evalResult = evaluateConfidenceBand(draft);
    ttsPlayer.playBandChime(evalResult.band);

    if (evalResult.autoCommit) {
      setUndoDraft(draft);
      activeUndoDraftRef.current = draft;
    } else {
      setHeldDrafts((prev) => [...prev.filter((d) => d.draft_id !== draft.draft_id), draft]);
    }
  }, []);

  useEffect(() => {
    db.outbox.get(1).then((rec) => {
      if (rec && typeof rec.device_id === 'string') setDeviceId(rec.device_id);
      else {
        const newDevId = `dev_${generateUlid().slice(0, 8)}`;
        setDeviceId(newDevId);
        db.outbox.put({ seq: 1, event_id: '', attempts: 0, next_retry_at: '', device_id: newDevId }).catch(() => {});
      }
    }).catch(() => {});

    draftMgrRef.current = new DraftManager({
      onDraftChange: (st) => setDraftState(st),
      onWindowExpired: (expiredDraft) => handleDraftEvaluated(expiredDraft),
    });

    queueRef.current = new JobQueueManager({
      onDraftReceived: (draft) => draftMgrRef.current?.updateWithUtterance(draft),
      onStatusChange: (inFlight, queued) => setQueueStats({ inFlight, queued }),
      onEmpty: () => ttsPlayer.onQueueEmpty(),
      onJobDegraded: (job) => setDegradedJob(job),
      onBackfillComplete: () => loadEvents(),
    });

    queueRef.current.init();
    loadEvents();
  }, [handleDraftEvaluated, loadEvents]);

  const handleAudioCaptured = useCallback(async (audio: RecordedAudio) => {
    const job: CaptureJob = {
      job_id: audio.jobId,
      shop_id: SHOP_ID,
      draft_id: draftMgrRef.current?.draftId ?? null,
      audio_blob_ref: audio.jobId,
      duration_ms: audio.durationMs,
      peak_rms: audio.peakRms,
      clip_ratio: audio.clipRatio,
      codec: audio.codec,
      captured_at: audio.capturedAt,
      created_at: audio.capturedAt,
      state: 'queued',
      attempts: 0,
      result_ref: null,
    };
    if (queueRef.current) await queueRef.current.enqueue(job, audio.blob);
  }, []);

  const handleManualOfflineCommit = useCallback(
    async (customerId: string | null, amount: number, isCash: boolean) => {
      if (!degradedJob) return;
      await commitManualOfflineSale(SHOP_ID, customerId, amount, isCash, degradedJob.job_id, deviceId);
      setDegradedJob(null);
      loadEvents();
    },
    [degradedJob, deviceId, loadEvents]
  );

  return {
    shopId: SHOP_ID,
    deviceId,
    events,
    heldDrafts,
    draftState,
    undoDraft,
    queueStats,
    isTrayOpen,
    degradedJob,
    setIsTrayOpen,
    handleAudioCaptured,
    handleDiscardDraft: () => draftMgrRef.current?.discard(),
    handleCommitDraftNow: () => {
      if (draftState.draft) {
        const d = draftState.draft;
        draftMgrRef.current?.commitDone();
        handleDraftEvaluated(d);
      }
    },
    handleUndo: () => {
      setUndoDraft(null);
      activeUndoDraftRef.current = null;
      draftMgrRef.current?.discard();
    },
    handleExpireUndo: () => {
      if (activeUndoDraftRef.current) executeCommit(activeUndoDraftRef.current);
    },
    handleCommitHeldDraft: async (draft: ParsedDraft) => {
      setHeldDrafts((prev) => prev.filter((d) => d.draft_id !== draft.draft_id));
      await executeCommit(draft);
    },
    handleRejectHeldDraft: (draftId: string) => setHeldDrafts((prev) => prev.filter((d) => d.draft_id !== draftId)),
    handleManualOfflineCommit,
    dismissDegradedJob: () => setDegradedJob(null),
    refreshEvents: loadEvents,
  };
}
