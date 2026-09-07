/**
 * TypeScript interfaces — mirrors docs/02-contracts.md section 2 exactly.
 *
 * Server-only fields intentionally omitted:
 *   ParsedDraft.residue, ParsedDraft.normalized_tokens, ParsedDraft.raw_texts
 */

export type Unit = 'kg' | 'g' | 'l' | 'ml' | 'dozen' | 'packet'
                 | 'bottle' | 'box' | 'piece';

export type MatchStatus = 'resolved' | 'ambiguous' | 'unknown' | 'provisional';
export type PriceSource = 'spoken' | 'catalogue' | 'missing';
export type OrderForm  = 'canonical' | 'name_last' | 'name_medial'
                       | 'no_name_draft' | 'no_name_cash';

export interface LineItem {
  sku_id: string | null;
  raw_name: string;
  display_name: string | null;
  qty: number | null;
  unit: Unit | null;
  spoken_amount: number | null;     // integer PKR, from MONEY token adjacent to line item
  unit_price: number | null;
  line_total: number | null;
  price_source: PriceSource;
  match_score: number;
  match_status: MatchStatus;
  candidates: string[];
  derived_fields: string[];
  token_span: [number, number];
}

export interface CustomerRef {
  customer_id: string | null;
  raw_name: string | null;
  status: 'resolved' | 'ambiguous' | 'unknown' | 'absent';
  confidence: number;
  candidates: string[];
  source: 'spoken' | 'open_draft' | 'cash_default';
}

export interface ValidationResult {
  passed: boolean;
  blocking: { rule: string; item_index: number | null; message: string }[];
  warnings: { rule: string; item_index: number | null; message: string }[];
  requires_llm: boolean;
}

export interface ParsedDraft {
  draft_id: string;
  job_ids: string[];
  shop_id: string;
  customer: CustomerRef;
  items: LineItem[];
  stated_total: number | null;
  computed_total: number;
  payment_type: 'cash' | 'udhaar';
  order_form: OrderForm;
  confidence: number;
  path: 'fast' | 'llm' | 'manual';
  validation: ValidationResult;
}

// ---------- client-only ----------

export interface CaptureJob {
  job_id: string;                 // ULID, generated at button release
  shop_id: string;
  draft_id: string | null;
  audio_blob_ref: string;
  duration_ms: number;
  peak_rms: number;
  clip_ratio: number;
  codec: string;
  captured_at: string;
  state: 'queued' | 'uploading' | 'processing' | 'done' | 'failed';
  attempts: number;
  result_ref: string | null;
}

export type LedgerEventType =
  | 'sale_udhaar' | 'sale_cash' | 'payment_received'
  | 'adjustment'  | 'reassign'
  | 'customer_created' | 'sku_created' | 'price_updated';

export interface LedgerEvent {
  event_id: string;               // ULID
  shop_id: string;
  device_id: string;
  lamport: number;
  type: LedgerEventType;
  customer_id: string | null;     // null for an unattributed cash sale
  amount: number;                 // signed integer PKR: +debt, -payment
  items: LineItem[];
  payload: Record<string, unknown>;
  corrects_event_id: string | null;
  audio_refs: string[];
  source: 'voice' | 'manual' | 'llm_repair';
  confidence: number;
  created_at: string;
  server_received_at: string | null;
  sync_state: 'pending' | 'in_flight' | 'synced' | 'failed';
  sync_attempts: number;
}
