import type { ParsedDraft } from '../types';
import { ALL_FIXTURES } from '../fixtures';

const BACKEND_URL = 'http://localhost:8000';

// Explicit flag gating: default false. Never fall back just because a request failed.
export const IS_DEMO_FIXTURES: boolean = import.meta.env.VITE_USE_FIXTURES === 'true';

export interface SendUtteranceParams {
  audioBlob: Blob;
  jobId: string;
  shopId: string;
  draftId: string | null;
  capturedAt: string;
  clientMeta: {
    codec: string;
    duration_ms: number;
    peak_rms: number;
    clip_ratio: number;
  };
}

let fixtureIndex = 0;

export async function sendUtterance(params: SendUtteranceParams): Promise<ParsedDraft> {
  // If explicitly in fixture mode, serve canned responses with explicit demo flag
  if (IS_DEMO_FIXTURES) {
    const template = ALL_FIXTURES[fixtureIndex % ALL_FIXTURES.length];
    fixtureIndex++;
    return {
      ...template,
      draft_id: params.draftId ?? `draft-${params.jobId.slice(0, 10)}`,
      job_ids: [params.jobId],
      shop_id: params.shopId,
      asr_engine: 'demo_fixture',
    };
  }

  // Normal live path: never fabricate a parse when backend is unreachable
  const formData = new FormData();
  formData.append('audio', params.audioBlob, 'audio.webm');
  formData.append('shop_id', params.shopId);
  formData.append('job_id', params.jobId);
  if (params.draftId) {
    formData.append('draft_id', params.draftId);
  }
  formData.append('captured_at', params.capturedAt);
  formData.append('client_meta', JSON.stringify(params.clientMeta));

  const res = await fetch(`${BACKEND_URL}/v1/utterance`, {
    method: 'POST',
    body: formData,
  });

  if (res.ok) {
    const parsed = (await res.json()) as ParsedDraft;
    return parsed;
  }

  if (res.status === 400) {
    const errJson = await res.json().catch(() => ({}));
    throw new Error(`400 Bad Request: ${errJson.message || 'audio rejected'}`);
  }

  if (res.status === 503) {
    throw new Error('503 ASR Unavailable');
  }

  throw new Error(`Server returned status ${res.status}`);
}
