/**
 * Dexie-backed audio job queue with concurrency limit (max 3),
 * exponential backoff, and reload survival.
 * Docs: docs/03-build-plan.md Phase 7; AGENTS.md rule 10.
 */

import { db } from '../db';
import type { CaptureJob, ParsedDraft } from '../types';

const MAX_IN_FLIGHT = 3;
let inFlightCount = 0;
let isProcessingQueue = false;

export type JobCallback = (draft: ParsedDraft, jobId: string) => void;
const subscribers = new Set<JobCallback>();

export function subscribeToJobSuccess(cb: JobCallback): () => void {
  subscribers.add(cb);
  return () => subscribers.delete(cb);
}

export async function enqueueJob(params: {
  job_id: string;
  shop_id: string;
  draft_id: string | null;
  audio_blob: Blob;
  duration_ms: number;
  peak_rms: number;
  clip_ratio: number;
  codec: string;
}): Promise<CaptureJob> {
  const now = new Date().toISOString();

  // Save audio blob in Dexie audio table
  await db.audio.put({
    job_id: params.job_id,
    blob: params.audio_blob,
    created_at: now,
  });

  const job: CaptureJob = {
    job_id: params.job_id,
    shop_id: params.shop_id,
    draft_id: params.draft_id,
    audio_blob_ref: params.job_id,
    duration_ms: params.duration_ms,
    peak_rms: params.peak_rms,
    clip_ratio: params.clip_ratio,
    codec: params.codec,
    captured_at: now,
    state: 'queued',
    attempts: 0,
    result_ref: null,
  };

  await db.jobs.put(job);
  triggerQueueDrain();
  return job;
}

export async function triggerQueueDrain(): Promise<void> {
  if (isProcessingQueue) return;
  isProcessingQueue = true;

  try {
    while (inFlightCount < MAX_IN_FLIGHT) {
      // Find oldest pending job
      const pendingJob = await db.jobs
        .where('state')
        .equals('queued')
        .sortBy('created_at')
        .then((jobs) => jobs[0]);

      if (!pendingJob) break;

      // Claim job
      await db.jobs.update(pendingJob.job_id, { state: 'uploading' });
      inFlightCount++;

      // Process in background without blocking loop
      processSingleJob(pendingJob).finally(() => {
        inFlightCount--;
        triggerQueueDrain();
      });
    }
  } finally {
    isProcessingQueue = false;
  }
}

async function processSingleJob(job: CaptureJob): Promise<void> {
  const audioRecord = await db.audio.get(job.job_id);
  if (!audioRecord) {
    await db.jobs.update(job.job_id, { state: 'failed' });
    return;
  }

  const formData = new FormData();
  formData.append('audio', audioRecord.blob, `utterance_${job.job_id}.${job.codec.includes('wav') ? 'wav' : 'webm'}`);
  formData.append('shop_id', job.shop_id);
  formData.append('job_id', job.job_id);
  if (job.draft_id) {
    formData.append('draft_id', job.draft_id);
  }
  formData.append('captured_at', job.captured_at);
  formData.append(
    'client_meta',
    JSON.stringify({
      codec: job.codec,
      duration_ms: job.duration_ms,
      peak_rms: job.peak_rms,
      clip_ratio: job.clip_ratio,
    })
  );

  try {
    await db.jobs.update(job.job_id, { state: 'processing' });
    const response = await fetch('/v1/utterance', {
      method: 'POST',
      body: formData,
    });

    if (response.ok) {
      const parsedDraft: ParsedDraft = await response.json();
      await db.drafts.put(parsedDraft);
      await db.jobs.update(job.job_id, {
        state: 'done',
        result_ref: parsedDraft.draft_id,
      });

      // Notify subscribers
      for (const cb of subscribers) {
        cb(parsedDraft, job.job_id);
      }
    } else {
      const isClientError = response.status >= 400 && response.status < 500 && response.status !== 409;
      if (isClientError) {
        await db.jobs.update(job.job_id, { state: 'failed' });
      } else {
        await handleJobRetry(job);
      }
    }
  } catch {
    // Network failure (offline, airplane mode) -> exponential backoff retry
    await handleJobRetry(job);
  }
}

async function handleJobRetry(job: CaptureJob): Promise<void> {
  const nextAttempts = job.attempts + 1;
  const backoffMs = Math.min(30000, 1000 * Math.pow(2, nextAttempts));

  await db.jobs.update(job.job_id, {
    state: 'queued',
    attempts: nextAttempts,
  });

  // Schedule retry after backoff
  setTimeout(() => {
    triggerQueueDrain();
  }, backoffMs);
}

