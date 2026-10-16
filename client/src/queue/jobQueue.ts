import { db } from '../db';
import type { CaptureJob, ParsedDraft } from '../types';
import { sendUtterance } from './api';
import { backfillOfflineSale } from '../ledger/events';

const MAX_IN_FLIGHT = 3;
const MAX_ATTEMPTS = 5;

export type DraftReceivedHandler = (draft: ParsedDraft, jobId: string) => void;
export type QueueStatusHandler = (inFlight: number, queued: number) => void;
export type QueueEmptyHandler = () => void;
export type JobDegradedHandler = (job: CaptureJob) => void;
export type BackfillCompleteHandler = (jobId: string, draft: ParsedDraft) => void;

export class JobQueueManager {
  private _inFlight = new Set<string>();
  private _running = false;
  private _onDraftReceived?: DraftReceivedHandler;
  private _onStatusChange?: QueueStatusHandler;
  private _onEmpty?: QueueEmptyHandler;
  private _onJobDegraded?: JobDegradedHandler;
  private _onBackfillComplete?: BackfillCompleteHandler;

  constructor(handlers?: {
    onDraftReceived?: DraftReceivedHandler;
    onStatusChange?: QueueStatusHandler;
    onEmpty?: QueueEmptyHandler;
    onJobDegraded?: JobDegradedHandler;
    onBackfillComplete?: BackfillCompleteHandler;
  }) {
    this._onDraftReceived = handlers?.onDraftReceived;
    this._onStatusChange = handlers?.onStatusChange;
    this._onEmpty = handlers?.onEmpty;
    this._onJobDegraded = handlers?.onJobDegraded;
    this._onBackfillComplete = handlers?.onBackfillComplete;

    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => this.pump());
    }
  }

  async init(): Promise<void> {
    await db.jobs.where('state').anyOf(['uploading', 'processing']).modify({ state: 'queued' });
    this.pump();
  }

  async enqueue(job: CaptureJob, audioBlob: Blob): Promise<void> {
    await db.audio.put({ job_id: job.job_id, blob: audioBlob });
    await db.jobs.put(job);
    this.pump();
  }

  async pump(): Promise<void> {
    if (this._running) return;
    this._running = true;

    try {
      while (this._inFlight.size < MAX_IN_FLIGHT) {
        const availableSlots = MAX_IN_FLIGHT - this._inFlight.size;
        const candidates = await db.jobs.where('state').equals('queued').limit(availableSlots).toArray();
        const pending = candidates.filter((j) => !this._inFlight.has(j.job_id));
        if (pending.length === 0) break;

        for (const job of pending) {
          if (this._inFlight.size >= MAX_IN_FLIGHT) break;
          this._inFlight.add(job.job_id);
          this._processJob(job).finally(() => {
            this._inFlight.delete(job.job_id);
            this.pump();
          });
        }
      }
    } finally {
      this._running = false;
      this._emitStatus();
    }
  }

  private async _processJob(job: CaptureJob): Promise<void> {
    try {
      await db.jobs.update(job.job_id, { state: 'uploading' });
      const audioRecord = await db.audio.get(job.job_id);
      if (!audioRecord || !audioRecord.blob) {
        await db.jobs.update(job.job_id, { state: 'failed' });
        return;
      }

      const draft = await sendUtterance({
        audioBlob: audioRecord.blob,
        jobId: job.job_id,
        shopId: job.shop_id,
        draftId: job.draft_id,
        capturedAt: job.captured_at,
        clientMeta: {
          codec: job.codec,
          duration_ms: job.duration_ms,
          peak_rms: job.peak_rms,
          clip_ratio: job.clip_ratio,
        },
      });

      await db.jobs.update(job.job_id, { state: 'done', result_ref: draft.draft_id });

      // Check if an offline manual sale event exists for this job_id waiting for backfill
      const allEvents = await db.events.toArray();
      const pendingEvent = allEvents.find(
        (e) => e.audio_refs?.includes(job.job_id) && e.payload?.pending_backfill === true
      );

      if (pendingEvent) {
        await backfillOfflineSale(pendingEvent, draft, job.shop_id);
        this._onBackfillComplete?.(job.job_id, draft);
      } else {
        this._onDraftReceived?.(draft, job.job_id);
      }
    } catch (err: unknown) {
      const attempts = (job.attempts || 0) + 1;
      const msg = err instanceof Error ? err.message : String(err);
      if (attempts >= MAX_ATTEMPTS || msg.startsWith('400')) {
        await db.jobs.update(job.job_id, { state: 'failed', attempts });
      } else {
        const backoffMs = Math.min(1000 * Math.pow(2, attempts), 30000);
        await db.jobs.update(job.job_id, { state: 'queued', attempts });
        setTimeout(() => this.pump(), backoffMs);
      }
      this._onJobDegraded?.(job);
    }
  }

  private async _emitStatus(): Promise<void> {
    const queuedCount = await db.jobs.where('state').equals('queued').count();
    this._onStatusChange?.(this._inFlight.size, queuedCount);
    if (this._inFlight.size === 0 && queuedCount === 0) {
      this._onEmpty?.();
    }
  }
}
