import { db } from '../db';
import type { LedgerEvent, ParsedDraft } from '../types';
import { generateUlid } from '../capture/ulid';

let globalLamport = 0;

export async function appendLedgerEvent(
  eventData: Omit<LedgerEvent, 'event_id' | 'lamport' | 'created_at' | 'sync_state' | 'sync_attempts' | 'server_received_at'>
): Promise<LedgerEvent> {
  globalLamport++;
  const event: LedgerEvent = {
    ...eventData,
    event_id: generateUlid(),
    lamport: globalLamport,
    amount: Math.round(eventData.amount), // Integer PKR -- AGENTS.md rule 1
    created_at: new Date().toISOString(),
    server_received_at: null,
    sync_state: 'pending',
    sync_attempts: 0,
  };

  // Rule 11: The ledger is append-only. Never UPDATE, never DELETE.
  await db.events.put(event);
  return event;
}

export async function commitDraftToLedger(
  draft: ParsedDraft,
  deviceId: string
): Promise<LedgerEvent> {
  const isCash = draft.payment_type === 'cash' || draft.customer.status === 'absent';
  const type = isCash ? 'sale_cash' : 'sale_udhaar';
  const amount = Math.round(draft.computed_total);

  return appendLedgerEvent({
    shop_id: draft.shop_id,
    device_id: deviceId,
    type,
    customer_id: isCash ? null : (draft.customer.customer_id ?? draft.customer.raw_name),
    amount,
    items: draft.items,
    payload: {
      draft_id: draft.draft_id,
      job_ids: draft.job_ids,
      order_form: draft.order_form,
      asr_engine: draft.asr_engine || 'groq',
    },
    corrects_event_id: null,
    audio_refs: draft.job_ids,
    source: draft.path === 'llm' ? 'llm_repair' : 'voice',
    confidence: draft.confidence,
  });
}

export async function commitManualOfflineSale(
  shopId: string,
  customerId: string | null,
  amountPkr: number,
  isCash: boolean,
  jobId: string,
  deviceId: string
): Promise<LedgerEvent> {
  return appendLedgerEvent({
    shop_id: shopId,
    device_id: deviceId,
    type: isCash ? 'sale_cash' : 'sale_udhaar',
    customer_id: isCash ? null : customerId,
    amount: Math.round(amountPkr),
    items: [],
    payload: {
      job_id: jobId,
      asr_engine: 'manual',
      pending_backfill: true,
      manual_entry: true,
    },
    corrects_event_id: null,
    audio_refs: [jobId],
    source: 'manual',
    confidence: 1.0,
  });
}

export async function backfillOfflineSale(
  originalEvent: LedgerEvent,
  draft: ParsedDraft,
  deviceId: string
): Promise<LedgerEvent> {
  return appendLedgerEvent({
    shop_id: originalEvent.shop_id,
    device_id: deviceId,
    type: 'adjustment',
    customer_id: originalEvent.customer_id,
    amount: 0,
    items: draft.items,
    payload: {
      backfilled_for: originalEvent.event_id,
      job_id: draft.job_ids[0] || (originalEvent.audio_refs[0] ?? ''),
      asr_engine: draft.asr_engine || 'groq',
      raw_texts: (draft as { raw_texts?: string[] }).raw_texts || [],
    },
    corrects_event_id: originalEvent.event_id,
    audio_refs: draft.job_ids.length > 0 ? draft.job_ids : originalEvent.audio_refs,
    source: draft.path === 'llm' ? 'llm_repair' : 'voice',
    confidence: draft.confidence,
  });
}

export async function recordPayment(
  shopId: string,
  customerId: string,
  amountPkr: number,
  deviceId: string
): Promise<LedgerEvent> {
  return appendLedgerEvent({
    shop_id: shopId,
    device_id: deviceId,
    type: 'payment_received',
    customer_id: customerId,
    amount: -Math.abs(Math.round(amountPkr)),
    items: [],
    payload: { asr_engine: 'manual' },
    corrects_event_id: null,
    audio_refs: [],
    source: 'manual',
    confidence: 1.0,
  });
}

export async function recordAdjustment(
  shopId: string,
  customerId: string,
  amountChange: number,
  reason: string,
  deviceId: string,
  correctsEventId: string | null = null
): Promise<LedgerEvent> {
  return appendLedgerEvent({
    shop_id: shopId,
    device_id: deviceId,
    type: 'adjustment',
    customer_id: customerId,
    amount: Math.round(amountChange),
    items: [],
    payload: { reason, asr_engine: 'manual' },
    corrects_event_id: correctsEventId,
    audio_refs: [],
    source: 'manual',
    confidence: 1.0,
  });
}
