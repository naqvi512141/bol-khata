/**
 * Dexie schema — mirrors docs/02-contracts.md section 9.
 * Rule 10: No localStorage, no sessionStorage. Only IndexedDB via Dexie.
 */

import Dexie, { type Table } from 'dexie';
import type { CaptureJob, LedgerEvent } from './types';

export class BolKhataDB extends Dexie {
  jobs!: Table<CaptureJob>;
  drafts!: Table;
  events!: Table<LedgerEvent>;
  customers!: Table;
  skus!: Table;
  prices!: Table;
  audio!: Table;
  outbox!: Table;

  constructor() {
    super('bolkhata');
    this.version(1).stores({
      jobs:      'job_id, state, created_at',
      drafts:    'draft_id, customer_id, opened_at',
      events:    'event_id, shop_id, customer_id, created_at, sync_state',
      customers: 'customer_id, folded_name, last_txn_at',
      skus:      'sku_id, folded_name, *aliases, provisional',
      prices:    '[sku_id+observed_at]',
      audio:     'job_id',
      outbox:    '++seq, event_id, attempts, next_retry_at',
    });
  }
}

export const db = new BolKhataDB();
