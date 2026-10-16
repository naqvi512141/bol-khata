/**
 * Ledger Service — append-only event store and balance fold logic.
 * AGENTS.md rules 1, 10, 11:
 * - Money is int PKR, always, everywhere.
 * - Append-only: never UPDATE, never DELETE.
 * - Balances are computed as a fold over events, never stored.
 */

import { db } from '../db';
import { generateULID } from '../lib/ulid';
import type { LedgerEvent, ParsedDraft } from '../types';

export interface CustomerBalance {
  customerId: string;
  displayName: string;
  balance: number; // integer PKR
  lastTxnAt: string | null;
  txnCount: number;
}

export interface DaySummaryData {
  totalCreditSales: number; // udhaar (int PKR)
  totalCashSales: number;   // cash (int PKR)
  totalPayments: number;    // wasooli (int PKR)
  txnCount: number;
}

export function computeBalancesFromEvents(
  events: LedgerEvent[],
  customerMap: Record<string, string> = {}
): Record<string, CustomerBalance> {
  const balances: Record<string, CustomerBalance> = {};
  const sorted = [...events].sort((a, b) => a.created_at.localeCompare(b.created_at));

  for (const ev of sorted) {
    const custId = ev.customer_id;
    if (!custId) continue;

    if (!balances[custId]) {
      balances[custId] = {
        customerId: custId,
        displayName: customerMap[custId] || custId,
        balance: 0,
        lastTxnAt: null,
        txnCount: 0,
      };
    }

    const current = balances[custId];
    current.txnCount += 1;
    current.lastTxnAt = ev.created_at;

    if (ev.type === 'sale_udhaar') {
      current.balance += Math.round(ev.amount);
    } else if (ev.type === 'payment_received') {
      current.balance -= Math.round(ev.amount);
    } else if (ev.type === 'adjustment') {
      current.balance += Math.round(ev.amount);
    }
  }

  return balances;
}

export function computeDaySummary(events: LedgerEvent[], targetDateStr?: string): DaySummaryData {
  const targetPrefix = targetDateStr || new Date().toISOString().slice(0, 10);
  let totalCredit = 0;
  let totalCash = 0;
  let totalPayments = 0;
  let count = 0;

  for (const ev of events) {
    if (ev.created_at.startsWith(targetPrefix)) {
      count++;
      if (ev.type === 'sale_udhaar') totalCredit += Math.round(ev.amount);
      else if (ev.type === 'sale_cash') totalCash += Math.round(ev.amount);
      else if (ev.type === 'payment_received') totalPayments += Math.round(ev.amount);
    }
  }

  return {
    totalCreditSales: totalCredit,
    totalCashSales: totalCash,
    totalPayments: totalPayments,
    txnCount: count,
  };
}

export async function commitDraftToLedger(
  draft: ParsedDraft,
  source: 'voice' | 'manual' | 'llm_repair' = 'voice',
  deviceId: string = 'device_client_01'
): Promise<LedgerEvent> {
  const event: LedgerEvent = {
    event_id: generateULID(),
    shop_id: draft.shop_id || 'demo_shop_01',
    device_id: deviceId,
    lamport: Date.now(),
    type: draft.payment_type === 'cash' ? 'sale_cash' : 'sale_udhaar',
    customer_id: draft.customer.customer_id,
    amount: Math.round(draft.computed_total), // int PKR -- AGENTS.md rule 1
    items: draft.items,
    payload: {
      order_form: draft.order_form,
      path: draft.path,
      stated_total: draft.stated_total,
    },
    corrects_event_id: null,
    audio_refs: draft.job_ids,
    source: source,
    confidence: draft.confidence,
    created_at: new Date().toISOString(),
    server_received_at: null,
    sync_state: 'pending',
    sync_attempts: 0,
  };

  await db.events.put(event);
  return event;
}

export async function recordPayment(customerId: string, amountPkr: number): Promise<LedgerEvent> {
  const event: LedgerEvent = {
    event_id: generateULID(),
    shop_id: 'demo_shop_01',
    device_id: 'device_client_01',
    lamport: Date.now(),
    type: 'payment_received',
    customer_id: customerId,
    amount: Math.round(amountPkr), // int PKR
    items: [],
    payload: {},
    corrects_event_id: null,
    audio_refs: [],
    source: 'manual',
    confidence: 1.0,
    created_at: new Date().toISOString(),
    server_received_at: null,
    sync_state: 'pending',
    sync_attempts: 0,
  };

  await db.events.put(event);
  return event;
}

export async function undoEvent(event: LedgerEvent): Promise<LedgerEvent> {
  const adjustmentEvent: LedgerEvent = {
    event_id: generateULID(),
    shop_id: event.shop_id,
    device_id: event.device_id,
    lamport: Date.now(),
    type: 'adjustment',
    customer_id: event.customer_id,
    amount: -event.amount, // Negates committed amount (int PKR)
    items: [],
    payload: { reason: '3-second undo button pressed', reversed_event_id: event.event_id },
    corrects_event_id: event.event_id,
    audio_refs: [],
    source: 'manual',
    confidence: 1.0,
    created_at: new Date().toISOString(),
    server_received_at: null,
    sync_state: 'pending',
    sync_attempts: 0,
  };

  await db.events.put(adjustmentEvent);
  return adjustmentEvent;
}

