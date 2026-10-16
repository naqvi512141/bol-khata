/**
 * Dexie schema — mirrors docs/02-contracts.md section 9.
 * Rule 10: No localStorage, no sessionStorage. Only IndexedDB via Dexie.
 */

import Dexie, { type Table } from 'dexie';
import type { CaptureJob, LedgerEvent, ParsedDraft } from './types';

export interface AudioRecord {
  job_id: string;
  blob: Blob;
  created_at: string;
}

export interface CustomerRecord {
  customer_id: string;
  folded_name: string;
  display_name: string;
  phone?: string | null;
  last_txn_at?: string | null;
}

export interface SKURecord {
  sku_id: string;
  folded_name: string;
  display_name: string;
  aliases: string[];
  default_unit: string;
  unit_price?: number | null;
  provisional: boolean;
}

export interface PriceRecord {
  sku_id: string;
  observed_at: string;
  price: number;
  qty: number;
}

export class BolKhataDB extends Dexie {
  jobs!: Table<CaptureJob, string>;
  drafts!: Table<ParsedDraft, string>;
  events!: Table<LedgerEvent, string>;
  customers!: Table<CustomerRecord, string>;
  skus!: Table<SKURecord, string>;
  prices!: Table<PriceRecord, [string, string]>;
  audio!: Table<AudioRecord, string>;
  outbox!: Table<{ seq?: number; event_id: string; attempts: number; next_retry_at: string }, number>;

  constructor() {
    super('bolkhata');
    this.version(1).stores({
      jobs:      'job_id, state, created_at',
      drafts:    'draft_id, customer.customer_id, opened_at',
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
